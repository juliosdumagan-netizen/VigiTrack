"""
Targeted tests for CameraManager concurrency and incident logging:
- _open_capture releases capture_lock during slow capture creation and aborts if source changed.
- zones_lock synchronizes set_zones / get_zones and worker consumption.
- Ownerless UNASSIGNED alerts log distance=None instead of distance_threshold.

Uses temporary data and a stubbed ObjectDetector so no camera or model weights are needed.
Run from the backend folder:  python tests/test_camera_manager.py
"""
import os
import sys
import tempfile
import threading
import time
import types

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

tmp = tempfile.mkdtemp(prefix="vt_cm_")
from config import settings_store  # noqa: E402
from app.database import db as db_mod  # noqa: E402
settings_store.SETTINGS_PATH = os.path.join(tmp, "settings.json")
db_mod.DB_PATH = os.path.join(tmp, "vigitrack.db")
db_mod.init_db()


class FakeDetector:
    next_detections: list = []

    def __init__(self, monitored_classes=None):
        self.monitored_classes = set(monitored_classes or ["person", "backpack"])

    def set_monitored_classes(self, class_names):
        self.monitored_classes = set(class_names) | {"person"}

    def detect_and_track(self, frame):
        return list(self.next_detections)


det_mod = types.ModuleType("app.detection.detector")
det_mod.ObjectDetector = FakeDetector  # type: ignore[attr-defined]
sys.modules["app.detection.detector"] = det_mod

from app.database.models import get_all_incidents  # noqa: E402
from app.stream.camera_manager import CameraManager  # noqa: E402

results = []


def check(name, cond, extra: object = ""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))


class FakeCap:
    def __init__(self):
        self.released = False

    def isOpened(self):
        return not self.released

    def read(self):
        return False, None

    def release(self):
        self.released = True


# --- 1. _open_capture must not hold capture_lock while _create_capture runs ---
cm = CameraManager(source="rtsp://127.0.0.1:554/dead", camera_name="TEST CAM",
                   distance_threshold=150, time_threshold=0.05)
lock_held_during_create = None


def slow_create(src):
    global lock_held_during_create
    lock_held_during_create = cm.capture_lock.locked()
    return FakeCap()


cm._create_capture = slow_create  # type: ignore[method-assign]
opened = cm._open_capture()
check("_open_capture succeeds with FakeCap", opened)
check("_open_capture does not hold capture_lock during _create_capture", lock_held_during_create is False,
      lock_held_during_create)
cm.stop()

# --- 2. _open_capture discards capture if source was switched mid-connect ---
cm2 = CameraManager(source="rtsp://127.0.0.1:554/old", camera_name="TEST CAM",
                    distance_threshold=150, time_threshold=0.05)
stale_cap = FakeCap()


def switching_create(src):
    cm2.source = "rtsp://127.0.0.1:554/new"
    return stale_cap


cm2._create_capture = switching_create  # type: ignore[method-assign]
opened_stale = cm2._open_capture()
check("_open_capture aborts when source changes during connect", opened_stale is False)
check("_open_capture releases stale capture when aborted", stale_cap.released is True)
check("_open_capture leaves cap untouched when aborted", cm2.cap is None)

# --- 3. Ownerless alert logs distance=None (not distance_threshold) ---
cm3 = CameraManager(source=0, camera_name="TEST CAM", distance_threshold=150, time_threshold=0.05)
cm3.notifier.set_audio_enabled(False)
FakeDetector.next_detections = [
    {"id": 42, "class_name": "backpack", "box": [100.0, 100.0, 160.0, 180.0], "confidence": 0.9}
]
cm3.running = True
worker = threading.Thread(target=cm3._process_loop, daemon=True)
worker.start()

frame = np.zeros((240, 320, 3), dtype=np.uint8)
deadline = time.time() + 2.0
incidents = []
while time.time() < deadline:
    with cm3.raw_frame_lock:
        cm3.raw_frame = frame
    cm3.has_new_raw_frame.set()
    time.sleep(0.03)
    incidents = get_all_incidents()
    if incidents:
        break

cm3.running = False
cm3.has_new_raw_frame.set()
worker.join(timeout=1.0)

check("ownerless bag alert creates an incident", len(incidents) == 1, len(incidents))
if incidents:
    inc = incidents[0]
    check("ownerless incident has person_track_id=None", inc["person_track_id"] is None, inc["person_track_id"])
    check("ownerless incident logs distance=None instead of threshold", inc["distance"] is None, inc["distance"])
else:
    check("ownerless incident has person_track_id=None", False)
    check("ownerless incident logs distance=None instead of threshold", False)

# --- 4. Zones update cleanly under zones_lock ---
zones = [{"id": "z1", "name": "Desk", "type": "ignore", "points": [[0.0, 0.0], [0.2, 0.0], [0.2, 0.2]]}]
saved = cm3.set_zones(zones)
got = cm3.get_zones()
check("zones round-trip through set_zones and get_zones", len(saved) == 1 and got["zones"] == saved, got)
check("frame size recorded after processing frame", got["frame"] == {"width": 320, "height": 240}, got["frame"])

passed = sum(results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
