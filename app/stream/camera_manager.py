import cv2
import threading
import time
from typing import Optional, List, Dict

from app.detection.detector import ObjectDetector
from app.detection.fsm_tracker import AdvancedBaggageMonitor
from app.alerts.notifier import Notifier
from app.database.models import log_incident
from config.settings_store import load_settings, save_settings


class CameraManager:
    """
    High-performance zero-lag surveillance camera orchestrator:
    - Dual-threaded design: Reader thread discards buffer latency; worker thread processes YOLO + FSM.
    - Real-time visualization: Green/red proximity lines, countdown timers, bounding boxes, alert banner.
    - Dynamic threshold updates and live camera source switching without restarting the server.
    """

    def __init__(self, source=None, camera_name=None,
                 distance_threshold=None, time_threshold=None):
        settings = load_settings()

        self.source = settings.get("camera_source", 0) if source is None else source
        if isinstance(self.source, str) and self.source.isdigit():
            self.source = int(self.source)

        self.camera_name = settings.get("camera_name", "BUILT-IN WEBCAM") if camera_name is None else camera_name
        self.distance_threshold = float(distance_threshold or settings.get("distance_threshold", 150))
        self.time_threshold = float(time_threshold or settings.get("time_threshold", 10))

        # Core subsystems
        self.detector = ObjectDetector()
        self.monitor = AdvancedBaggageMonitor(
            distance_threshold=self.distance_threshold,
            time_threshold=self.time_threshold
        )
        self.notifier = Notifier(audio_enabled=settings.get("audio_alert_enabled", True))

        # Threading state
        self.cap: Optional[cv2.VideoCapture] = None
        self.raw_frame = None
        self.raw_frame_lock = threading.Lock()
        self.has_new_raw_frame = threading.Event()

        self.latest_jpeg = None
        self.jpeg_lock = threading.Lock()

        self.running = False
        self.capture_thread: Optional[threading.Thread] = None
        self.process_thread: Optional[threading.Thread] = None

        # Alert debouncing & tracking
        self.logged_bag_ids = set()
        self.recent_alerts: List[Dict] = []
        self.alerts_lock = threading.Lock()
        self.max_recent_alerts = 25

    def start(self):
        """Starts video capture and inference pipelines."""
        if self.running:
            return

        self._open_capture()
        self.running = True

        self.capture_thread = threading.Thread(target=self._reader_loop, daemon=True, name="VigiTrack-Reader")
        self.process_thread = threading.Thread(target=self._process_loop, daemon=True, name="VigiTrack-Worker")

        self.capture_thread.start()
        self.process_thread.start()
        print(f"[CameraManager] Streaming initialized on source '{self.source}' ({self.camera_name})")

    def stop(self):
        """Cleanly stops processing and releases the camera."""
        self.running = False
        self.has_new_raw_frame.set()

        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=1.0)
        if self.process_thread and self.process_thread.is_alive():
            self.process_thread.join(timeout=1.0)

        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        print("[CameraManager] Camera stopped successfully.")

    def _open_capture(self):
        """Opens cv2.VideoCapture with optimal buffer settings."""
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass

        if isinstance(self.source, int):
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.source)
        else:
            self.cap = cv2.VideoCapture(self.source)

        if self.cap and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        else:
            print(f"[CameraManager Warning] Failed to open capture source: {self.source}")

    def _reader_loop(self):
        """Dedicated thread to constantly drain OpenCV frame buffers and eliminate lag."""
        reconnect_attempts = 0
        while self.running:
            if not self.cap or not self.cap.isOpened():
                time.sleep(0.5)
                self._open_capture()
                continue

            ret, frame = self.cap.read()
            if not ret or frame is None:
                reconnect_attempts += 1
                time.sleep(0.05)
                if reconnect_attempts > 40:
                    print(f"[CameraManager] Reconnecting to camera source '{self.source}'...")
                    self._open_capture()
                    reconnect_attempts = 0
                continue

            reconnect_attempts = 0
            with self.raw_frame_lock:
                self.raw_frame = frame
            self.has_new_raw_frame.set()

    def _process_loop(self):
        """Worker thread executing YOLO inference, FSM logic, and annotation."""
        while self.running:
            try:
                self.has_new_raw_frame.wait(timeout=0.1)
                self.has_new_raw_frame.clear()

                with self.raw_frame_lock:
                    if self.raw_frame is None:
                        continue
                    frame = self.raw_frame.copy()

                # 1. Run YOLOv8 + ByteTrack
                detections = self.detector.detect_and_track(frame)

                # 2. Update FSM State Machine Proximity Pipeline
                telemetry = self.monitor.update(detections)

                # 3. Draw Detections & Overlays
                any_alert = False

                # Draw Person detections
                for det in detections:
                    if det["class_name"] == "person":
                        x1, y1, x2, y2 = map(int, det["box"])
                        track_id = det["id"]
                        conf = det["confidence"]
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 180, 0), 2)
                        lbl = f"Person #{track_id} ({conf:.2f})"
                        cv2.putText(frame, lbl, (x1, max(20, y1 - 8)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 180, 0), 2, cv2.LINE_AA)

                # Draw Baggage and Proximity lines
                for item in telemetry:
                    bid = item["bag_id"]
                    cls_name = item["class_name"]
                    state = item["state"]
                    is_alert = item["is_alert"]
                    bx, by = map(int, item["bag_center"])
                    ow_center = item["owner_center"]
                    dist = item["distance"]
                    countdown = item["countdown"]

                    # Locate bounding box with fallback to smoothed tracklet box
                    bag_det = next((d for d in detections if d["id"] == bid and d["class_name"] == cls_name), None)
                    if bag_det:
                        bx1, by1, bx2, by2 = map(int, bag_det["box"])
                    elif "box" in item and item["box"]:
                        bx1, by1, bx2, by2 = map(int, item["box"])
                    else:
                        bx1, by1, bx2, by2 = bx - 30, by - 30, bx + 30, by + 30

                    # Determine color based on state
                    if is_alert:
                        any_alert = True
                        box_color = (0, 0, 255)  # Red
                    elif state in ("SEPARATED", "OWNER_OUT_OF_VIEW") or (state == "UNASSIGNED" and countdown > 0):
                        box_color = (0, 165, 255)  # Orange (Countdown active)
                    elif state in ("CARRIED", "STATIC_ATTENDED"):
                        box_color = (0, 255, 0)  # Green
                    else:
                        box_color = (200, 200, 200)

                    thickness = 1 if item.get("is_persisted") else 2
                    cv2.rectangle(frame, (bx1, by1), (bx2, by2), box_color, thickness)

                    # Draw proximity line between bag and owner if owner exists
                    if ow_center is not None:
                        ox, oy = map(int, ow_center)
                        line_color = (0, 255, 0) if dist <= self.monitor.distance_threshold else (0, 0, 255)
                        cv2.line(frame, (bx, by), (ox, oy), line_color, 2, cv2.LINE_AA)

                        mx, my = (bx + ox) // 2, (by + oy) // 2
                        cv2.putText(frame, f"{int(dist)}px", (mx, my - 6),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, line_color, 1, cv2.LINE_AA)

                    # Status label & countdown
                    if is_alert:
                        label = f"UNATTENDED {cls_name.upper()} #{bid}"
                        cv2.putText(frame, label, (bx1, max(25, by1 - 10)),
                                    cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)

                        self.notifier.play_alert_sound(bid)
                        if bid not in self.logged_bag_ids:
                            log_incident(
                                object_class=cls_name,
                                object_track_id=bid,
                                person_track_id=item["owner_id"],
                                distance=dist if dist > 0 else self.monitor.distance_threshold,
                                camera_name=self.camera_name
                            )
                            self.logged_bag_ids.add(bid)
                            self._record_alert(cls_name, bid)

                    elif state in ("SEPARATED", "OWNER_OUT_OF_VIEW"):
                        label = f"{cls_name.capitalize()} #{bid} | Timer: {countdown:.1f}s"
                        cv2.putText(frame, label, (bx1, max(20, by1 - 8)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2, cv2.LINE_AA)
                    elif state == "UNASSIGNED" and countdown > 0:
                        label = f"{cls_name.capitalize()} #{bid} (No Owner) | Timer: {countdown:.1f}s"
                        cv2.putText(frame, label, (bx1, max(20, by1 - 8)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2, cv2.LINE_AA)
                    else:
                        label = f"{cls_name.capitalize()} #{bid}"
                        cv2.putText(frame, label, (bx1, max(20, by1 - 8)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2, cv2.LINE_AA)

                # Draw visual alert banner if any unattended object is active
                if any_alert:
                    frame = self.notifier.draw_alert_banner(frame)

                # Encode frame to JPEG
                ret_enc, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                if ret_enc:
                    with self.jpeg_lock:
                        self.latest_jpeg = buffer.tobytes()

            except Exception as e:
                print(f"[CameraManager Worker Error] {e}")
                time.sleep(0.05)

    def _record_alert(self, object_class: str, object_id: int):
        """Records an alert entry for the live web dashboard."""
        alert_entry = {
            "message": f"ALERT: {object_class.capitalize()} (Track #{object_id}) unattended!",
            "time": time.strftime("%I:%M:%S %p"),
            "camera": self.camera_name
        }
        with self.alerts_lock:
            self.recent_alerts.insert(0, alert_entry)
            self.recent_alerts = self.recent_alerts[:self.max_recent_alerts]

    def get_frame(self) -> Optional[bytes]:
        """Returns the latest encoded JPEG frame."""
        with self.jpeg_lock:
            return self.latest_jpeg

    def get_recent_alerts(self) -> List[Dict]:
        """Returns a snapshot of the most recent alerts."""
        with self.alerts_lock:
            return list(self.recent_alerts)

    def get_thresholds(self) -> Dict:
        """Returns active distance and time thresholds."""
        return {
            "distance_threshold": self.monitor.distance_threshold,
            "time_threshold": self.monitor.time_threshold,
            "camera_source": self.source,
            "camera_name": self.camera_name,
            "audio_alert_enabled": self.notifier.audio_enabled
        }

    def update_thresholds(self, distance_threshold: float, time_threshold: float):
        """Updates distance and time thresholds dynamically without restarting."""
        d = float(distance_threshold)
        t = float(time_threshold)
        self.distance_threshold = d
        self.time_threshold = t
        self.monitor.distance_threshold = d
        self.monitor.time_threshold = t

        settings = load_settings()
        settings["distance_threshold"] = d
        settings["time_threshold"] = t
        save_settings(settings)
        print(f"[CameraManager] Updated thresholds: Distance={d}px, Time={t}s")

    def switch_source(self, new_source, new_camera_name=None):
        """Dynamically switches camera source."""
        if isinstance(new_source, str) and new_source.isdigit():
            new_source = int(new_source)

        if self.source == new_source:
            return

        print(f"[CameraManager] Switching source from {self.source} to {new_source}")
        self.source = new_source
        if new_camera_name:
            self.camera_name = new_camera_name

        self._open_capture()

        settings = load_settings()
        settings["camera_source"] = self.source
        if new_camera_name:
            settings["camera_name"] = self.camera_name
        save_settings(settings)
