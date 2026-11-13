import json
import os
import sqlite3
import sys
import tempfile
import time
import types

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

tmp = tempfile.mkdtemp(prefix="vt2_")
settings_path = os.path.join(tmp, "settings.json")
db_path = os.path.join(tmp, "vigitrack.db")

from config import settings_store
from app.database import db as db_mod
settings_store.SETTINGS_PATH = settings_path
db_mod.DB_PATH = db_path

class FakeNotifier:
    audio_enabled = True
    def set_audio_enabled(self, v):
        self.audio_enabled = v

class FakeCameraManager:
    def __init__(self, *a, **k):
        s = settings_store.load_settings()
        self.source = s.get("camera_source", 0)
        self.camera_name = s.get("camera_name", "BUILT-IN WEBCAM")
        self.notifier = FakeNotifier()
    def start(self):
        pass
    def get_thresholds(self):
        return {"distance_threshold": 150, "time_threshold": 10, "camera_source": self.source,
                "camera_name": self.camera_name, "audio_alert_enabled": True}
    def update_thresholds(self, d, t):
        pass
    def switch_source(self, new, name=None):
        pass

stub = types.ModuleType("app.stream.camera_manager")
stub.CameraManager = FakeCameraManager
sys.modules["app.stream.camera_manager"] = stub

results = []
def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))

# --- 1. Migration on an old-schema database ---
old = sqlite3.connect(db_path)
old.execute("""CREATE TABLE incidents (id INTEGER PRIMARY KEY AUTOINCREMENT, object_class TEXT NOT NULL,
    object_track_id INTEGER, person_track_id INTEGER, distance REAL, camera_name TEXT,
    status TEXT DEFAULT 'unattended', detected_at TEXT NOT NULL)""")
old.execute("INSERT INTO incidents (object_class, object_track_id, person_track_id, distance, camera_name, status, detected_at) VALUES ('backpack', 4, 2, 200.0, 'OLD', 'unattended', '2026-11-10T10:00:00')")
old.commit()
old.close()

import run  # noqa: E402  (also runs init_db via create_app)
app = run.create_app()
client = app.test_client()

cols = {r[1] for r in sqlite3.connect(db_path).execute("PRAGMA table_info(incidents)")}
check("migration adds new columns", {"image_path", "state_history", "distance_threshold", "time_threshold"} <= cols)

from app.database.models import log_incident, get_incident, INCIDENT_IMAGE_DIR
legacy = get_incident(1)
check("legacy row readable after migration", legacy is not None and legacy["image_url"] is None and legacy["state_history"] == [])

# --- 2. Logging with snapshot and state history ---
jpeg = b"\xff\xd8\xff\xe0FAKEJPEG\xff\xd9"
history = [{"time": "2026-11-12T23:00:00.000", "state": "STATIC_ATTENDED"},
           {"time": "2026-11-12T23:00:05.000", "state": "SEPARATED"},
           {"time": "2026-11-12T23:00:15.000", "state": "UNATTENDED_ALERT"}]
new_id = log_incident("suitcase", 101, 3, 180.0, "BUILT-IN WEBCAM", image_bytes=jpeg,
                      state_history=history, distance_threshold=150, time_threshold=10)
check("incident with snapshot inserted", new_id is not None)
img_file = os.path.join(INCIDENT_IMAGE_DIR, f"{new_id}.jpg")
check("snapshot file written", os.path.exists(img_file))

no_img_id = log_incident("handbag", 7, None, None, "BUILT-IN WEBCAM")

# --- 3. Endpoints ---
anon = app.test_client()
check("image endpoint requires login", anon.get(f"/api/incidents/{new_id}/image").status_code == 401)
check("detail endpoint requires login", anon.get(f"/api/incidents/{new_id}").status_code == 401)

from app.database import users as _acc
_code = _acc._setup_state["code"] or _acc.prepare_first_run()
client.post("/api/setup", json={"setup_code": _code, "username": "admin", "password": "admin123"})

rows = client.get("/api/incidents").get_json()
by_id = {r["id"]: r for r in rows}
check("list includes image_url", by_id[new_id]["image_url"] == f"/api/incidents/{new_id}/image")
check("list has no raw image_path", "image_path" not in by_id[new_id])
check("list has parsed state_history", by_id[new_id]["state_history"] == history)
check("legacy row has null image_url", by_id[1]["image_url"] is None)

detail = client.get(f"/api/incidents/{new_id}")
check("detail returns 200", detail.status_code == 200)
d = detail.get_json()
check("detail has thresholds", d["distance_threshold"] == 150 and d["time_threshold"] == 10)
check("detail has object fields", d["object_class"] == "suitcase" and d["object_track_id"] == 101)

img = client.get(f"/api/incidents/{new_id}/image")
check("image served as jpeg", img.status_code == 200 and img.mimetype == "image/jpeg", img.status_code)
check("image bytes match", img.data == jpeg)
img.close()

check("missing incident is 404", client.get("/api/incidents/9999").status_code == 404)
check("no-snapshot incident image is 404", client.get(f"/api/incidents/{no_img_id}/image").status_code == 404)
check("legacy incident image is 404", client.get("/api/incidents/1/image").status_code == 404)

# --- 4. Cleanup on delete and clear ---
client.delete(f"/api/incidents/{new_id}")
check("delete removes snapshot file", not os.path.exists(img_file))

again = log_incident("backpack", 9, None, None, "BUILT-IN WEBCAM", image_bytes=jpeg)
again_file = os.path.join(INCIDENT_IMAGE_DIR, f"{again}.jpg")
client.post("/api/incidents/clear")
check("clear removes snapshot files", not os.path.exists(again_file))
check("clear empties table", client.get("/api/incidents").get_json() == [])

# --- 5. FSM records state history ---
from app.detection.fsm_tracker import AdvancedBaggageMonitor
mon = AdvancedBaggageMonitor(distance_threshold=150, time_threshold=0.2)
bag_near = {"id": 1, "class_name": "backpack", "box": [100, 100, 120, 120], "confidence": 0.9}
person_near = {"id": 2, "class_name": "person", "box": [90, 60, 130, 140], "confidence": 0.9}
person_far = {"id": 2, "class_name": "person", "box": [600, 100, 640, 300], "confidence": 0.9}
for _ in range(3):
    mon.update([bag_near, person_near])
for _ in range(2):
    mon.update([bag_near, person_far])
time.sleep(0.25)
out = mon.update([bag_near, person_far])
bag_out = next(t for t in out if t["bag_id"] == 1)
states = [h["state"] for h in bag_out["state_history"]]
check("telemetry includes state_history", isinstance(bag_out["state_history"], list) and len(states) > 0, states)
check("history records attended then alert", "STATIC_ATTENDED" in states and states[-1] == "UNATTENDED_ALERT", states)
check("history entries are time-stamped", all("time" in h for h in bag_out["state_history"]))

passed = sum(1 for _, ok in results if ok)
print(f"\n{passed}/{len(results)} checks passed")

