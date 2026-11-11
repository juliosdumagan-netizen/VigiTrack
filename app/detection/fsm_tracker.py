"""
VigiTrack - Finite State Machine Baggage Tracking Pipeline
Calibrated for real-world surveillance:
- Proximity-based ownership binding (seated & stationary owners properly recognized).
- Tracklet persistence & spatial re-ID to prevent tracker ID jumping.
- Handbag/Backpack cross-class spatial recovery: prevents track reset when YOLO
  toggles between 'handbag' and 'backpack' across frames.
- Temporal smoothing: keeps tracked bags visible during 10-12 frame detector dropouts.
- Hysteresis distance line (Green when attended, Red when separated).
- Separation countdown only triggers when owner truly walks away or exits frame.
"""

import math
import time
from enum import Enum
from collections import deque
from typing import List, Dict, Optional, Tuple


class BaggageState(Enum):
    UNASSIGNED = "UNASSIGNED"
    CARRIED = "CARRIED"
    STATIC_ATTENDED = "STATIC_ATTENDED"
    SEPARATED = "SEPARATED"
    OWNER_OUT_OF_VIEW = "OWNER_OUT_OF_VIEW"
    UNATTENDED_ALERT = "UNATTENDED_ALERT"


class BaggageTracklet:
    """Maintains state, trajectory, ownership lock, and countdown timer for an item."""

    def __init__(self, track_id: int, class_name: str, initial_box: List[float],
                 history_len: int = 15):
        self.track_id: int = track_id
        self.class_name: str = class_name
        self.current_box: List[float] = initial_box
        self.state: BaggageState = BaggageState.UNASSIGNED

        self.centroid_history: deque = deque(maxlen=history_len)
        self.owner_id: Optional[int] = None
        self.owner_last_seen_pos: Optional[Tuple[float, float]] = None
        self.owner_missing_frames: int = 0

        self.separation_start_time: Optional[float] = None
        self.attended_streak: int = 0
        self.lost_frames: int = 0
        self.candidate_owner_streaks: Dict[int, int] = {}

        cx = (initial_box[0] + initial_box[2]) / 2.0
        cy = (initial_box[1] + initial_box[3]) / 2.0
        self.centroid_history.append((cx, cy))

    @property
    def current_centroid(self) -> Tuple[float, float]:
        return self.centroid_history[-1]

    def update_position(self, box: List[float]):
        self.current_box = box
        cx = (box[0] + box[2]) / 2.0
        cy = (box[1] + box[3]) / 2.0
        self.centroid_history.append((cx, cy))
        self.lost_frames = 0

    def is_static(self, variance_threshold: float = 12.0) -> bool:
        """Stationary check based on centroid spatial variance."""
        if len(self.centroid_history) < 4:
            return True
        pts = list(self.centroid_history)
        mean_x = sum(p[0] for p in pts) / len(pts)
        mean_y = sum(p[1] for p in pts) / len(pts)
        variance = sum((p[0] - mean_x)**2 + (p[1] - mean_y)**2 for p in pts) / len(pts)
        return variance < variance_threshold


class AdvancedBaggageMonitor:
    """Manages ownership association, proximity evaluation, and unattended alerts."""

    def __init__(self,
                 distance_threshold: float = 150.0,
                 time_threshold: float = 10.0,
                 attended_confirm_frames: int = 3,
                 max_track_lost_frames: int = 45,
                 persist_telemetry_frames: int = 15):

        self.distance_threshold = float(distance_threshold)
        self.time_threshold = float(time_threshold)
        self.attended_confirm_frames = attended_confirm_frames
        self.max_track_lost_frames = max_track_lost_frames
        self.persist_telemetry_frames = persist_telemetry_frames

        self.baggage_pool: Dict[int, BaggageTracklet] = {}

    @staticmethod
    def _get_centroid(box: List[float]) -> Tuple[float, float]:
        return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)

    @staticmethod
    def _distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    def _find_spatial_match(self, centroid: Tuple[float, float], class_name: str, max_dist: float = 85.0) -> Optional[int]:
        """
        Recovers existing tracklet if tracker swapped its ID.
        Supports cross-bag matching: if an item was previously detected as 'backpack'
        and is now seen as 'handbag', it seamlessly maintains the existing track!
        """
        best_id = None
        best_dist = float("inf")
        bag_classes = {"backpack", "handbag", "suitcase"}

        for bid, bag in self.baggage_pool.items():
            if bag.lost_frames > 0:
                is_compatible = (bag.class_name == class_name) or (
                    bag.class_name in bag_classes and class_name in bag_classes
                )
                if is_compatible:
                    d = self._distance(centroid, bag.current_centroid)
                    if d < max_dist and d < best_dist:
                        best_dist = d
                        best_id = bid
        return best_id

    def update(self, detections: List[Dict]) -> List[Dict]:
        now = time.time()
        people = [d for d in detections if d["class_name"] == "person"]
        bags = [d for d in detections if d["class_name"] in ("backpack", "handbag", "suitcase")]

        active_canonical_ids = set()
        telemetry = []

        # 1. Update / Recover Baggage Tracklets with Canonical ID Locking
        for b_det in bags:
            det_id = b_det["id"]
            box = b_det["box"]
            cls_name = b_det["class_name"]
            centroid = self._get_centroid(box)

            if det_id in self.baggage_pool:
                canonical_id = det_id
                self.baggage_pool[canonical_id].class_name = cls_name
                self.baggage_pool[canonical_id].update_position(box)
            else:
                recovered_id = self._find_spatial_match(centroid, cls_name)
                if recovered_id is not None:
                    # PRESERVE THE CANONICAL ID: Do not overwrite with det_id!
                    canonical_id = recovered_id
                    self.baggage_pool[canonical_id].class_name = cls_name
                    self.baggage_pool[canonical_id].update_position(box)
                else:
                    canonical_id = det_id
                    self.baggage_pool[canonical_id] = BaggageTracklet(canonical_id, cls_name, box)

            active_canonical_ids.add(canonical_id)

        # 2. Advance lost-frame counters for missing bags
        for bid in list(self.baggage_pool.keys()):
            if bid not in active_canonical_ids:
                self.baggage_pool[bid].lost_frames += 1
                if self.baggage_pool[bid].lost_frames > self.max_track_lost_frames:
                    del self.baggage_pool[bid]

        # 3. Process FSM logic for all active and persisting bag tracklets
        for bid, bag in list(self.baggage_pool.items()):
            if bag.lost_frames > self.persist_telemetry_frames:
                continue

            bag_center = bag.current_centroid
            bag_static = bag.is_static()

            # STEP A: OWNER ASSOCIATION
            if bag.owner_id is None:
                nearest_person_id = None
                nearest_dist = float("inf")

                for p_det in people:
                    p_center = self._get_centroid(p_det["box"])
                    dist = self._distance(bag_center, p_center)
                    if dist <= self.distance_threshold and dist < nearest_dist:
                        nearest_dist = dist
                        nearest_person_id = p_det["id"]

                if nearest_person_id is not None:
                    streak = bag.candidate_owner_streaks.get(nearest_person_id, 0) + 1
                    bag.candidate_owner_streaks[nearest_person_id] = streak

                    if streak >= 2:
                        bag.owner_id = nearest_person_id
                        bag.state = BaggageState.STATIC_ATTENDED if bag_static else BaggageState.CARRIED
                        bag.separation_start_time = None
                else:
                    bag.candidate_owner_streaks.clear()
                    bag.state = BaggageState.UNASSIGNED

            # STEP B: EVALUATE ATTENDED / SEPARATED STATUS
            assigned_owner = next((p for p in people if p["id"] == bag.owner_id), None)
            owner_center = None
            measured_distance = -1.0

            if assigned_owner is not None:
                bag.owner_missing_frames = 0
                owner_center = self._get_centroid(assigned_owner["box"])
                bag.owner_last_seen_pos = owner_center
                measured_distance = self._distance(bag_center, owner_center)

                if measured_distance <= self.distance_threshold:
                    bag.attended_streak += 1
                    if bag.attended_streak >= self.attended_confirm_frames:
                        bag.separation_start_time = None
                        bag.state = BaggageState.STATIC_ATTENDED if bag_static else BaggageState.CARRIED
                else:
                    bag.attended_streak = 0
                    if bag.separation_start_time is None:
                        bag.separation_start_time = now

                    elapsed = now - bag.separation_start_time
                    if elapsed >= self.time_threshold:
                        bag.state = BaggageState.UNATTENDED_ALERT
                    else:
                        bag.state = BaggageState.SEPARATED

            elif bag.owner_id is not None:
                # OWNER HAS EXITED THE CAMERA FRAME
                bag.owner_missing_frames += 1
                bag.attended_streak = 0

                retrieved = False
                if not bag_static:
                    for p_det in people:
                        p_cen = self._get_centroid(p_det["box"])
                        if self._distance(bag_center, p_cen) < (self.distance_threshold * 0.5):
                            bag.owner_id = p_det["id"]
                            bag.separation_start_time = None
                            bag.state = BaggageState.CARRIED
                            retrieved = True
                            break

                if not retrieved:
                    if bag.separation_start_time is None:
                        bag.separation_start_time = now

                    elapsed = now - bag.separation_start_time
                    if elapsed >= self.time_threshold:
                        bag.state = BaggageState.UNATTENDED_ALERT
                    else:
                        bag.state = BaggageState.OWNER_OUT_OF_VIEW

                    owner_center = bag.owner_last_seen_pos
                    measured_distance = self.distance_threshold + 50.0

            else:
                if bag.separation_start_time is None:
                    bag.separation_start_time = now

                elapsed = now - bag.separation_start_time
                if elapsed >= self.time_threshold:
                    bag.state = BaggageState.UNATTENDED_ALERT
                else:
                    bag.state = BaggageState.UNASSIGNED

            time_remaining = 0.0
            elapsed_time = 0.0
            if bag.separation_start_time is not None:
                elapsed_time = now - bag.separation_start_time
                time_remaining = max(0.0, self.time_threshold - elapsed_time)

            telemetry.append({
                "bag_id": bid,  # Locked Canonical ID
                "class_name": bag.class_name,
                "box": bag.current_box,
                "state": bag.state.value,
                "owner_id": bag.owner_id,
                "bag_center": bag_center,
                "owner_center": owner_center,
                "distance": measured_distance,
                "elapsed": elapsed_time,
                "countdown": time_remaining,
                "is_static": bag_static,
                "is_alert": bag.state == BaggageState.UNATTENDED_ALERT,
                "is_persisted": bag.lost_frames > 0
            })

        return telemetry
