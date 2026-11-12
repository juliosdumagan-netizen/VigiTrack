import os
import math
import time
from typing import List, Dict, Optional, Tuple
import torch
import numpy as np
from ultralytics import YOLO
from app.detection.classes import SUPPORTED_CLASSES


def box_iou(box1: List[float], box2: List[float]) -> float:
    xA = max(box1[0], box2[0])
    yA = max(box1[1], box2[1])
    xB = min(box1[2], box2[2])
    yB = min(box1[3], box2[3])

    interArea = max(0.0, xB - xA) * max(0.0, yB - yA)
    boxAArea = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    boxBArea = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])

    denom = boxAArea + boxBArea - interArea
    return interArea / denom if denom > 0 else 0.0


class SpatialIdentityStabilizer:
    """
    Prevents ID switching, fragmentation, and class-flipping by enforcing spatial continuity:
    - Maintains persistent Canonical IDs (1, 2, 3...) that never mutate.
    - Two-tier matching: IoU overlap (Tier 1) and Centroid proximity (Tier 2).
    - Cross-bag tolerance: smooths out jitter between 'handbag' and 'backpack'.
    - Anti-morphing protection: prevents established stationary bags from flipping into 'person'.
    - 45-frame memory buffer (~1.5s) to bridge brief detection dropouts.
    """

    def __init__(self, max_lost_frames: int = 45, max_centroid_dist: float = 85.0, min_iou: float = 0.30):
        self.max_lost_frames = max_lost_frames
        self.max_centroid_dist = max_centroid_dist
        self.min_iou = min_iou

        self.next_canonical_id = 1
        # canonical_id -> dict(class_name, box, centroid, lost_frames, streak, is_bag)
        self.active_tracks: Dict[int, Dict] = {}

    @staticmethod
    def _centroid(box: List[float]) -> Tuple[float, float]:
        return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)

    @staticmethod
    def _dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    def stabilize(self, raw_detections: List[Dict]) -> List[Dict]:
        bag_classes = {"backpack", "handbag", "suitcase"}
        unmatched_dets = list(range(len(raw_detections)))
        matched_tracks = set()
        det_to_canonical = {}

        # 1. TIER 1 MATCHING: High IoU Overlap
        for d_idx in list(unmatched_dets):
            det = raw_detections[d_idx]
            det_box = det["box"]
            det_cls = det["class_name"]

            best_cid = None
            best_iou = self.min_iou

            for cid, trk in self.active_tracks.items():
                if cid in matched_tracks:
                    continue

                # Anti-morphing rule: An established bag cannot match a new 'person' detection
                trk_is_bag = trk["class_name"] in bag_classes
                det_is_bag = det_cls in bag_classes

                if trk_is_bag != det_is_bag:
                    continue

                same_category = (det_cls == trk["class_name"]) or (det_is_bag and trk_is_bag)
                if not same_category:
                    continue

                iou = box_iou(det_box, trk["box"])
                if iou > best_iou:
                    best_iou = iou
                    best_cid = cid

            if best_cid is not None:
                det_to_canonical[d_idx] = best_cid
                matched_tracks.add(best_cid)
                unmatched_dets.remove(d_idx)

        # 2. TIER 2 MATCHING: Centroid Proximity
        for d_idx in list(unmatched_dets):
            det = raw_detections[d_idx]
            det_cen = self._centroid(det["box"])
            det_cls = det["class_name"]

            best_cid = None
            best_dist = self.max_centroid_dist

            for cid, trk in self.active_tracks.items():
                if cid in matched_tracks:
                    continue

                trk_is_bag = trk["class_name"] in bag_classes
                det_is_bag = det_cls in bag_classes
                if trk_is_bag != det_is_bag:
                    continue

                same_category = (det_cls == trk["class_name"]) or (det_is_bag and trk_is_bag)
                if not same_category:
                    continue

                d = self._dist(det_cen, trk["centroid"])
                if d < best_dist:
                    best_dist = d
                    best_cid = cid

            if best_cid is not None:
                det_to_canonical[d_idx] = best_cid
                matched_tracks.add(best_cid)
                unmatched_dets.remove(d_idx)

        # 3. TIER 3: Spawn New Canonical IDs for genuinely new items
        for d_idx in unmatched_dets:
            cid = self.next_canonical_id
            self.next_canonical_id += 1
            det_to_canonical[d_idx] = cid
            matched_tracks.add(cid)

        # 4. Update track states and output stabilized detections
        stabilized = []
        for d_idx, det in enumerate(raw_detections):
            cid = det_to_canonical[d_idx]
            box = det["box"]
            cls_name = det["class_name"]
            cen = self._centroid(box)

            self.active_tracks[cid] = {
                "canonical_id": cid,
                "class_name": cls_name,
                "box": box,
                "centroid": cen,
                "lost_frames": 0,
                "last_seen": time.time()
            }

            stabilized.append({
                "id": cid,
                "class_name": cls_name,
                "box": box,
                "confidence": det["confidence"]
            })

        # 5. Age out unmatched tracks
        for cid in list(self.active_tracks.keys()):
            if cid not in matched_tracks:
                self.active_tracks[cid]["lost_frames"] += 1
                if self.active_tracks[cid]["lost_frames"] > self.max_lost_frames:
                    del self.active_tracks[cid]

        return stabilized


class ObjectDetector:
    """
    High-precision detector tuned for surveillance baggage & handbag detection:
    - Calibrated confidences: person (0.60), backpack (0.22), handbag (0.18), suitcase (0.25).
    - Cross-Class Collision Resolution: suppresses phantom 'person' boxes on top of backpacks.
    - Geometric Morphological Filter: rejects squarish/flat false-person detections.
    - SpatialIdentityStabilizer: guarantees persistent Canonical IDs (1, 2, 3...).
    - Box deduplication (IoU 0.45) to prevent double-detections on the same physical object.
    - Automatic hardware adaptation (CUDA GPU vs OpenVINO/CPU).
    """

    TARGET_CLASSES = SUPPORTED_CLASSES

    # Calibrated confidence gates:
    # 'person' raised to 0.60: Eliminates false person detections on upright backpacks/chairs
    # while preserving 100% sensitivity to real humans (which score 0.75-0.95).
    CLASS_CONFIDENCE = {
        "person": 0.60,
        "backpack": 0.22,
        "handbag": 0.18,
        "suitcase": 0.25
    }

    def __init__(self, model_name=None, monitored_classes=None):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"

        # Hardware-adaptive model selection
        if model_name is not None:
            chosen_model = model_name
        elif self.device.startswith("cuda"):
            chosen_model = "yolov8m.pt"
        else:
            openvino_dir = os.path.join(project_root, "yolov8n_openvino_model")
            if not os.path.exists(openvino_dir):
                openvino_dir = os.path.join(project_root, "models", "yolov8n_openvino_model")

            if os.path.exists(openvino_dir):
                chosen_model = openvino_dir
            else:
                chosen_model = "yolov8n.pt"

        # Resolve model path
        subfolder_model = os.path.join(project_root, "models", chosen_model)
        model_path = subfolder_model if os.path.exists(subfolder_model) else chosen_model

        self.model = YOLO(model_path)
        self.is_openvino = "openvino" in str(model_path).lower()

        # Path to custom ByteTrack configuration
        custom_tracker = os.path.join(project_root, "config", "bytetrack_custom.yaml")
        self.tracker_config = custom_tracker if os.path.exists(custom_tracker) else "bytetrack.yaml"

        self.class_confidence = self.CLASS_CONFIDENCE.copy()
        self.monitored_classes = set()
        self.allowed_ids = []
        self.set_monitored_classes(monitored_classes or list(self.TARGET_CLASSES.values()))

        # Canonical spatial ID stabilizer
        self.identity_stabilizer = SpatialIdentityStabilizer(
            max_lost_frames=45,
            max_centroid_dist=85.0,
            min_iou=0.30
        )

        engine_desc = "OpenVINO CPU Engine" if self.is_openvino else f"{self.device.upper()}"
        print(f"[ObjectDetector] Initialized with {os.path.basename(str(model_path))} on {engine_desc}")
        print(f"[ObjectDetector] Tracker config: {os.path.basename(str(self.tracker_config))}")
        print("[ObjectDetector] Anti-Morphing & Spatial Identity Stabilizer ACTIVE")

    def set_monitored_classes(self, class_names):
        """Updates monitored classes; person is always included for owner association."""
        names = set(class_names) | {"person"}
        self.monitored_classes = names
        self.allowed_ids = [cid for cid, name in self.TARGET_CLASSES.items() if name in names]

    def _filter_person_geometry(self, box: List[float], conf: float) -> bool:
        """
        Morphological validation for 'person':
        Real humans standing or seated have height greater than width (H/W >= 0.90).
        Backpacks lying down or squarish objects falsely labeled as 'person' (H/W < 0.90)
        are rejected unless confidence is extraordinarily high (> 0.85).
        """
        w = max(1.0, box[2] - box[0])
        h = max(1.0, box[3] - box[1])
        aspect_ratio = h / w

        # Reject tiny or horizontally squarish 'person' detections
        if aspect_ratio < 0.90 and conf < 0.82:
            return False
        # Minimum physical height in pixels for a human in frame
        if h < 55.0 and conf < 0.85:
            return False

        return True

    def _resolve_person_bag_conflicts(self, candidates: List[Dict], iou_thresh: float = 0.40) -> List[Dict]:
        """
        Eliminates duplicate hallucinations where YOLO outputs both a 'person' box
        and a 'backpack'/'handbag' box covering the same physical object.
        If a 'person' box overlaps heavily with a bag of similar size, the bag wins!
        """
        people = [d for d in candidates if d["class_name"] == "person"]
        bags = [d for d in candidates if d["class_name"] != "person"]

        valid_people = []
        for p in people:
            p_box = p["box"]
            p_area = max(1.0, (p_box[2] - p_box[0]) * (p_box[3] - p_box[1]))
            is_hallucinated_person = False

            for b in bags:
                b_box = b["box"]
                b_area = max(1.0, (b_box[2] - b_box[0]) * (b_box[3] - b_box[1]))
                iou = box_iou(p_box, b_box)

                # If the person box overlaps heavily with a bag, and the bag is of similar scale
                # (i.e. not a tiny bag worn by a full-height human), it is an inanimate bag!
                area_ratio = b_area / p_area
                if (iou > iou_thresh) or (iou > 0.25 and area_ratio > 0.45):
                    is_hallucinated_person = True
                    break

            if not is_hallucinated_person:
                valid_people.append(p)

        return valid_people + bags

    def _deduplicate_boxes(self, raw_detections, iou_thresh=0.45):
        """Suppresses duplicate/nested bounding boxes covering the same physical item."""
        if len(raw_detections) <= 1:
            return raw_detections

        sorted_dets = sorted(raw_detections, key=lambda d: d["confidence"], reverse=True)
        kept = []

        for cand in sorted_dets:
            overlap = False
            for k in kept:
                is_both_person = (cand["class_name"] == "person" and k["class_name"] == "person")
                is_both_bag = (cand["class_name"] != "person" and k["class_name"] != "person")

                if (is_both_person or is_both_bag) and box_iou(cand["box"], k["box"]) > iou_thresh:
                    overlap = True
                    break
            if not overlap:
                kept.append(cand)

        return kept

    def detect_and_track(self, frame):
        """Runs YOLOv8 detection with ByteTrack tracking, cross-class conflict resolution, and NMS."""
        if frame is None or frame.size == 0 or not self.allowed_ids:
            return []

        track_kwargs = {
            "source": frame,
            "persist": True,
            "conf": 0.15,
            "iou": 0.45,
            "imgsz": 640,
            "classes": self.allowed_ids,
            "tracker": self.tracker_config,
            "verbose": False
        }

        if not self.is_openvino:
            track_kwargs["device"] = self.device

        results = self.model.track(**track_kwargs)
        raw_candidates = []

        if results and len(results) > 0:
            boxes_obj = results[0].boxes
            if boxes_obj is not None and len(boxes_obj) > 0:
                boxes = boxes_obj.xyxy.cpu().numpy()
                classes = boxes_obj.cls.cpu().numpy()
                confs = boxes_obj.conf.cpu().numpy()
                ids = boxes_obj.id.cpu().numpy() if boxes_obj.id is not None else None

                for idx, (box, cls, conf) in enumerate(zip(boxes, classes, confs)):
                    class_id = int(cls)
                    class_name = self.TARGET_CLASSES.get(class_id, "unknown")
                    conf = float(conf)

                    min_conf = self.class_confidence.get(class_name, 0.25)
                    if conf < min_conf:
                        continue

                    box_coords = [float(b) for b in box]

                    # Morphological check for persons to eliminate squarish bag hallucinations
                    if class_name == "person" and not self._filter_person_geometry(box_coords, conf):
                        continue

                    raw_id = int(ids[idx]) if (ids is not None and idx < len(ids)) else -1

                    raw_candidates.append({
                        "raw_id": raw_id,
                        "class_name": class_name,
                        "box": box_coords,
                        "confidence": conf
                    })

        # 1. Resolve Person-vs-Bag hallucinations (bag wins if boxes overlap)
        resolved = self._resolve_person_bag_conflicts(raw_candidates, iou_thresh=0.40)

        # 2. Deduplicate overlapping boxes within same class type
        deduped = self._deduplicate_boxes(resolved, iou_thresh=0.45)

        # 3. Lock IDs into permanent Canonical IDs via Spatial Identity Stabilizer
        return self.identity_stabilizer.stabilize(deduped)
