"""
Phase 1 checks: incident review, idle session timeout, camera status, and live monitored-class changes.
Uses temporary data and a stubbed camera. Run from the backend folder:
    python tests/test_phase1.py
"""
import json
import os
import sys
import tempfile
import time
import types

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

tmp = tempfile.mkdtemp(prefix="vt_p1_")
settings_path = os.path.join(tmp, "settings.json")
db_path = os.path.join(tmp, "vigitrack.db")

from config import settings_store  # noqa: E402
from app.database import db as db_mod  # noqa: E402
settings_store.SETTINGS_PATH = settings_path
db_mod.DB_PATH = db_path


class FakeNotifier:
    audio_enabled = True

    def set_audio_enabled(self, v):
        self.audio_enabled = v


class FakeCameraManager:
    def __init__(self, *a, **k):
        s = settings_store.load_settings()
        self.monitored = set(s.get("monitored_classes", ["person"]))
        self.notifier = FakeNotifier()

    def start(self):
        pass

    def get_thresholds(self):
        return {"distance_threshold": 150, "time_threshold": 10, "camera_source": 0,
                "camera_name": "TEST CAM", "audio_alert_enabled": True,
                "monitored_classes": sorted(self.monitored)}

    def update_thresholds(self, d, t):
        pass

    def switch_source(self, new, name=None):
        pass

    def get_recent_alerts(self):
        return []

    def get_camera_status(self):
        return {"status": "online", "last_frame_age": 0.1, "camera_name": "TEST CAM", "source": 0}

    def set_monitored_classes(self, names):
        self.monitored = set(names) | {"person"}
        self.calls.append(sorted(names))


FakeCameraManager.calls = []

stub = types.ModuleType("app.stream.camera_manager")
stub.CameraManager = FakeCameraManager
sys.modules["app.stream.camera_manager"] = stub

import run  # noqa: E402
from app.database import users as accounts  # noqa: E402
from app.database.models import log_incident  # noqa: E402
from app.stream import routes  # noqa: E402
from app.stream.camera_health import classify  # noqa: E402

results = []


def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))


app = run.create_app()
accounts.create_user("boss", "bosspass1", "admin")
accounts.create_user("guard", "guardpass1", "operator")

admin = app.test_client()
admin.post("/api/login", json={"username": "boss", "password": "bosspass1"})
operator = app.test_client()
operator.post("/api/login", json={"username": "guard", "password": "guardpass1"})
anon = app.test_client()

# --- 1. Incident review ---
incident_id = log_incident(object_class="handbag", object_track_id=5, person_track_id=2, distance=180,
                           camera_name="TEST CAM", image_bytes=None, state_history=[],
                           distance_threshold=150, time_threshold=10)
check("new incident starts as open", operator.get(f"/api/incidents/{incident_id}").get_json()["review_status"] == "open")

url = f"/api/incidents/{incident_id}/review"
r = operator.post(url, json={"action": "acknowledged"})
body = r.get_json()
check("operator acknowledges an incident", r.status_code == 200 and body["incident"]["review_status"] == "acknowledged",
      r.status_code)
check("review records who reviewed it", body["incident"]["reviewed_by"] == "guard" and body["incident"]["reviewed_at"])

r = operator.post(url, json={"action": "verified", "note": "Real bag left at the bench"})
check("operator verifies an incident with a note",
      r.status_code == 200 and r.get_json()["incident"]["review_note"] == "Real bag left at the bench")

r = operator.post(url, json={"action": "dismissed"})
check("dismissing as false alarm without a reason is refused", r.status_code == 400, r.get_json())

r = operator.post(url, json={"action": "dismissed", "note": "Student sitting with bag"})
check("dismissing with a reason succeeds",
      r.status_code == 200 and r.get_json()["incident"]["review_status"] == "dismissed")

r = operator.post(url, json={"action": "deleted"})
check("unknown review action is refused", r.status_code == 400)

r = operator.post(url, json={"action": "acknowledged", "note": "x" * 501})
check("overlong note is refused", r.status_code == 400)

r = operator.post(f"/api/incidents/{incident_id + 999}/review", json={"action": "acknowledged"})
check("reviewing a missing incident returns 404", r.status_code == 404)

r = operator.post(url, data="action=acknowledged", content_type="text/plain")
check("review rejects non-JSON requests", r.status_code == 415)

r = anon.post(url, json={"action": "acknowledged"})
check("review requires login", r.status_code == 401)

r = admin.post(url, json={"action": "acknowledged"})
check("admin can also review incidents", r.status_code == 200)

listed = next(i for i in operator.get("/api/incidents").get_json() if i["id"] == incident_id)
check("incident list shows the review status", listed["review_status"] == "acknowledged")

audit = admin.get("/api/audit").get_json()
check("review is recorded in the audit log",
      any(a["action"] == "incident_reviewed" and f"#{incident_id} → dismissed" in (a["detail"] or "") for a in audit))

# --- 2. Idle session timeout ---
routes.IDLE_TIMEOUT_SECONDS = 1

idle = app.test_client()
idle.post("/api/login", json={"username": "guard", "password": "guardpass1"})
end = time.time() + 1.6
while time.time() < end:
    idle.get("/api/alerts")  # background polling, must not count as activity
    time.sleep(0.3)
check("background polling alone does not keep a session alive",
      idle.get("/api/me").status_code == 401)

active = app.test_client()
active.post("/api/login", json={"username": "guard", "password": "guardpass1"})
end = time.time() + 1.6
ok_while_active = True
while time.time() < end:
    if active.get("/api/me").status_code != 200:
        ok_while_active = False
    time.sleep(0.3)
check("user activity keeps a session alive past the idle limit", ok_while_active)
check("session still valid after the active period", active.get("/api/me").status_code == 200)

routes.IDLE_TIMEOUT_SECONDS = 30 * 60

# The admin and operator sessions were idle during the 1-second test window, so they expired too.
# Log them in again, as a real user would.
admin = app.test_client()
admin.post("/api/login", json={"username": "boss", "password": "bosspass1"})
operator = app.test_client()
operator.post("/api/login", json={"username": "guard", "password": "guardpass1"})

audit = admin.get("/api/audit").get_json()
check("idle expiry is recorded in the audit log", any(a["action"] == "session_expired" for a in audit))

# --- 3. Camera status ---
now = 1000.0
check("no frames ever received is offline", classify(None, now) == ("offline", None))
check("frame 0.5 s ago is online", classify(now - 0.5, now)[0] == "online")
check("frame 3 s ago is reconnecting", classify(now - 3.0, now)[0] == "reconnecting")
check("frame 9 s ago is still reconnecting", classify(now - 9.0, now)[0] == "reconnecting")
check("frame 10 s ago is offline", classify(now - 10.0, now)[0] == "offline")

r = operator.get("/api/camera/status")
check("camera status endpoint returns the status", r.status_code == 200 and r.get_json()["status"] == "online")
check("camera status requires login", anon.get("/api/camera/status").status_code == 401)

# --- 4. Monitored classes apply without restart ---
r = admin.post("/api/settings", json={"monitored_classes": ["handbag", "person"]})
check("admin changes monitored classes", r.status_code == 200, r.get_json())
check("change is applied to the running detector", FakeCameraManager.calls[-1] == ["handbag", "person"],
      str(FakeCameraManager.calls))
check("change is saved for the next start", "handbag" in settings_store.load_settings()["monitored_classes"])

r = admin.post("/api/settings", json={"monitored_classes": ["person", "laptop"]})
check("unknown class is refused", r.status_code == 400 and "Unknown class: laptop" in r.get_json()["message"], r.get_json())

r = admin.post("/api/settings", json={"monitored_classes": "handbag"})
check("non-list value is refused", r.status_code == 400)

r = operator.post("/api/settings", json={"monitored_classes": ["handbag"]})
check("operator cannot change monitored classes", r.status_code == 403)

passed = sum(results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
