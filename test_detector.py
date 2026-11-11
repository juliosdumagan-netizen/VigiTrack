import sys
import types
from enum import IntEnum

# Compatibility guard for PyTorch 2.5+ legacy datapipes imports if needed
try:
    import torch.utils.data.datapipes  # type: ignore
except (ImportError, ModuleNotFoundError):
    try:
        import torch.utils.data as tud  # type: ignore

        class SHARDING_PRIORITIES(IntEnum):
            DEFAULT = 1

        sharding_mod = types.ModuleType("torch.utils.data.datapipes.iter.sharding")
        sharding_mod.SHARDING_PRIORITIES = SHARDING_PRIORITIES  # type: ignore

        iter_mod = types.ModuleType("torch.utils.data.datapipes.iter")
        iter_mod.sharding = sharding_mod  # type: ignore

        dp_mod = types.ModuleType("torch.utils.data.datapipes")
        dp_mod.iter = iter_mod  # type: ignore

        tud.datapipes = dp_mod  # type: ignore
        sys.modules["torch.utils.data.datapipes"] = dp_mod
        sys.modules["torch.utils.data.datapipes.iter"] = iter_mod
        sys.modules["torch.utils.data.datapipes.iter.sharding"] = sharding_mod
    except Exception:
        pass

import time
import cv2
import torch

from app.detection.detector import ObjectDetector
from app.detection.fsm_tracker import AdvancedBaggageMonitor
from app.alerts.notifier import Notifier
from config.settings_store import load_settings


def main():
    print("=" * 65)
    print("  VigiTrack: Standalone Detector & Proximity Test Harness")
    print("=" * 65)

    # 1. Device check
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        print(f"[Hardware] CUDA Acceleration ACTIVE on GPU: {gpu_name}")
    else:
        print("[Hardware] WARNING: CUDA not detected, running on CPU.")

    # 2. Settings & Camera Source
    settings = load_settings()
    source = settings.get("camera_source", 0)
    if isinstance(source, str) and source.isdigit():
        source = int(source)

    distance_thresh = float(settings.get("distance_threshold", 150))
    time_thresh = float(settings.get("time_threshold", 10))

    print(f"[Config] Source: {source}")
    print(f"[Config] Distance Threshold: {distance_thresh}px | Time Threshold: {time_thresh}s")
    print("[Config] Target Classes: Person (0), Backpack (24), Handbag (26), Suitcase (28)")

    # 3. Open Video Capture
    print(f"[Camera] Opening video source {source}...")
    if isinstance(source, int):
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(source)
    else:
        cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"[ERROR] Could not open camera source {source}!")
        print("Please check that your webcam or camera is plugged in and not in use by another app.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # 4. Initialize AI Models
    print("[AI Pipeline] Initializing YOLOv8 and ByteTrack...")
    detector = ObjectDetector(model_name="yolov8m.pt")
    monitor = AdvancedBaggageMonitor(
        distance_threshold=distance_thresh,
        time_threshold=time_thresh
    )
    notifier = Notifier(audio_enabled=settings.get("audio_alert_enabled", True))

    print("\n[READY] Video feed active! Controls:")
    print("  - Press 'Q' or 'ESC' to close the test window.\n")

    prev_time = time.time()
    fps = 0.0

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            print("[Camera] No frame received, waiting...")
            time.sleep(0.05)
            continue

        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(1e-5, now - prev_time))
        prev_time = now

        # 1. Detection and ByteTrack tracking
        detections = detector.detect_and_track(frame)

        # 2. Update Proximity State Machine
        telemetry = monitor.update(detections)

        any_alert = False

        # Draw Person boxes (Cyan/Blue)
        for det in detections:
            if det["class_name"] == "person":
                x1, y1, x2, y2 = map(int, det["box"])
                pid = det["id"]
                conf = det["confidence"]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 180, 0), 2)
                cv2.putText(frame, f"Person #{pid} ({conf:.2f})", (x1, max(20, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 180, 0), 2, cv2.LINE_AA)

        # Draw Baggage boxes & Proximity lines
        for item in telemetry:
            bid = item["bag_id"]
            cls_name = item["class_name"]
            state = item["state"]
            is_alert = item["is_alert"]
            dist = item["distance"]
            countdown = item["countdown"]
            bx, by = map(int, item["bag_center"])
            ow_center = item["owner_center"]

            # Locate bounding box with fallback to smoothed tracklet box
            b_det = next((d for d in detections if d["id"] == bid and d["class_name"] == cls_name), None)
            if b_det:
                bx1, by1, bx2, by2 = map(int, b_det["box"])
            elif "box" in item and item["box"]:
                bx1, by1, bx2, by2 = map(int, item["box"])
            else:
                bx1, by1, bx2, by2 = bx - 25, by - 25, bx + 25, by + 25

            # Box color
            if is_alert:
                any_alert = True
                box_color = (0, 0, 255)  # Red
            elif state in ("SEPARATED", "OWNER_OUT_OF_VIEW") or (state == "UNASSIGNED" and countdown > 0):
                box_color = (0, 165, 255)  # Orange (Countdown in progress)
            elif state in ("CARRIED", "STATIC_ATTENDED"):
                box_color = (0, 255, 0)  # Green (Attended)
            else:
                box_color = (200, 200, 200)

            thickness = 1 if item.get("is_persisted") else 2
            cv2.rectangle(frame, (bx1, by1), (bx2, by2), box_color, thickness)

            # Draw proximity line if owner is visible
            if ow_center is not None:
                ox, oy = map(int, ow_center)
                line_color = (0, 255, 0) if dist <= monitor.distance_threshold else (0, 0, 255)
                cv2.line(frame, (bx, by), (ox, oy), line_color, 2, cv2.LINE_AA)
                mx, my = (bx + ox) // 2, (by + oy) // 2
                cv2.putText(frame, f"{int(dist)}px", (mx, my - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, line_color, 1, cv2.LINE_AA)

            # Baggage labels
            if is_alert:
                cv2.putText(frame, f"UNATTENDED {cls_name.upper()} #{bid}!", (bx1, max(25, by1 - 10)),
                            cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)
                notifier.play_alert_sound(bid)
            elif state in ("SEPARATED", "OWNER_OUT_OF_VIEW"):
                cv2.putText(frame, f"{cls_name.capitalize()} #{bid} | Timer: {countdown:.1f}s",
                            (bx1, max(20, by1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2, cv2.LINE_AA)
            elif state == "UNASSIGNED" and countdown > 0:
                cv2.putText(frame, f"{cls_name.capitalize()} #{bid} (No Owner) | Timer: {countdown:.1f}s",
                            (bx1, max(20, by1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2, cv2.LINE_AA)
            else:
                cv2.putText(frame, f"{cls_name.capitalize()} #{bid}", (bx1, max(20, by1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2, cv2.LINE_AA)

        # Draw alert banner if active
        if any_alert:
            frame = notifier.draw_alert_banner(frame)

        # Overlay FPS & status HUD
        hud_text = f"FPS: {fps:.1f} | Dev: {'CUDA' if torch.cuda.is_available() else 'CPU'}"
        cv2.putText(frame, hud_text, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2, cv2.LINE_AA)

        cv2.imshow("VigiTrack - Standalone Test Detector (Press Q to quit)", frame)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q'), 27):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("[Camera] Test finished cleanly.")


if __name__ == "__main__":
    main()
