import csv
import io
import os
import sys
import tempfile
import types
from datetime import date, timedelta

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)
getattr(sys.stdout, "reconfigure", lambda **_: None)(encoding="utf-8")  # audit details use arrows

tmp = tempfile.mkdtemp(prefix="vt_audit_")
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
    """Stands in for the camera. Switching persists the source the way the real manager does."""
    def __init__(self, *a, **k):
        s = settings_store.load_settings()
        self.source = s.get("camera_source", 0)
        self.camera_name = s.get("camera_name", "BUILT-IN WEBCAM")
        self.notifier = FakeNotifier()
    def start(self):
        pass
    def get_thresholds(self):
        s = settings_store.load_settings()
        return {"distance_threshold": s.get("distance_threshold", 150), "time_threshold": s.get("time_threshold", 10),
                "camera_source": self.source, "camera_name": self.camera_name, "audio_alert_enabled": True,
                "monitored_classes": s.get("monitored_classes", [])}
    def update_thresholds(self, d, t):
        pass
    def set_monitored_classes(self, classes):
        pass
    def switch_source(self, new, name=None):
        from config.secret_store import store_camera_source
        s = settings_store.load_settings()
        store_camera_source(s, new)
        if name:
            s["camera_name"] = name
        settings_store.save_settings(s)
        self.source = new
    def get_zones(self):
        return {"zones": settings_store.load_settings().get("zones", []), "frame": None}
    def set_zones(self, zones):
        from app.detection.zones import normalise_zones
        cleaned = normalise_zones(zones)
        s = settings_store.load_settings()
        s["zones"] = cleaned
        settings_store.save_settings(s)
        return cleaned

stub = types.ModuleType("app.stream.camera_manager")
stub.CameraManager = FakeCameraManager  # type: ignore
sys.modules["app.stream.camera_manager"] = stub

results = []
def check(name, cond, extra: object = ""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))

import run  # noqa: E402
app = run.create_app()
anon = app.test_client()
admin = app.test_client()

from app.database import users as acc
from app.database.models import log_incident

_code = acc._setup_state["code"] or acc.prepare_first_run()
admin.post("/api/setup", json={"setup_code": _code, "username": "admin", "password": "admin123"})

admin.post("/api/users", json={"username": "ops", "password": "operator123", "role": "operator"})
ops = app.test_client()
ops.post("/api/login", json={"username": "ops", "password": "operator123"})
ops.post("/api/me/password", json={"current_password": "operator123", "new_password": "operator456"})
ops.post("/api/login", json={"username": "ops", "password": "operator456"})

def latest(action):
    rows, _ = acc.search_audit(action=action, limit=1)
    return rows[0]["detail"] if rows else None

# --- 1. Access ---
check("audit search requires login", anon.get("/api/audit/search").status_code == 401)
check("operator cannot read the audit trail", ops.get("/api/audit/search").status_code == 403)
check("operator cannot export the audit trail", ops.get("/api/audit/export.csv").status_code == 403)

# --- 2. Settings: old and new values ---
admin.post("/api/settings", json={"distance_threshold": 200, "time_threshold": 10})
check("threshold change records old and new values",
      latest("settings_changed") == "distance threshold (px) 150 → 200", latest("settings_changed"))

admin.post("/api/settings", json={"audio_alert_enabled": True, "distance_threshold": 200, "time_threshold": 10})
check("unchanged submit is recorded as no change", latest("settings_changed") == "no value changed")

admin.post("/api/settings", json={"monitored_classes": ["person", "backpack", "laptop"]})
check("monitored-class change has its own entry",
      latest("monitored_classes_changed") == "backpack, handbag, person, suitcase → backpack, laptop, person",
      latest("monitored_classes_changed"))

# --- 3. Camera switch: separate entry, credentials masked ---
secret_url = "rtsp://viewer:TopSecret123@192.168.1.50:554/stream1"
admin.post("/api/settings", json={"camera_source": secret_url, "camera_name": "LOBBY NVR"})
switched = latest("camera_switched")
check("camera switch has its own entry", switched is not None and "LOBBY NVR" in switched, switched)
check("RTSP password is never written to the audit log",
      all("TopSecret123" not in (r["detail"] or "") for r in acc.search_audit(limit=200)[0]))
check("camera source is shown masked", switched is not None and "***@" in switched, switched)

# --- 4. Zones: names of what changed ---
desk = {"id": "zone-1", "name": "Reception desk", "type": "ignore", "points": [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4]]}
door = {"id": "zone-2", "name": "Front door", "type": "watch", "time_threshold": 4,
        "points": [[0.7, 0.7], [0.95, 0.7], [0.95, 0.95]]}
admin.post("/api/zones", json={"zones": [desk, door]})
check("zone save names the zones added",
      latest("zones_updated") == "added Reception desk (ignore); added Front door (watch 4.0 s)", latest("zones_updated"))
renamed = dict(desk, name="Desk")
admin.post("/api/zones", json={"zones": [renamed]})
check("zone save names removed and edited zones",
      latest("zones_updated") == "removed Front door (watch 4.0 s); edited Reception desk (ignore) → Desk (ignore)",
      latest("zones_updated"))

# --- 5. Snapshot views ---
jpeg = b"\xff\xd8\xff\xe0FAKEJPEG\xff\xd9"
inc = log_incident("backpack", 5, None, 120.0, "LOBBY", image_bytes=jpeg)
view = admin.get(f"/api/incidents/{inc}/image")
view.close()
check("snapshot view is recorded with the incident", latest("snapshot_viewed") == f"#{inc}", latest("snapshot_viewed"))
no_image = log_incident("handbag", 6, None, 90.0, "LOBBY")
admin.get(f"/api/incidents/{no_image}/image")
check("a request with no snapshot is not recorded as a view",
      sum(1 for r in acc.search_audit(action="snapshot_viewed", limit=200)[0] if r["detail"] == f"#{no_image}") == 0)

# --- 6. Search: filters, paging, dates ---
rows, total = acc.search_audit(action="snapshot_viewed", limit=50)
check("action filter returns only that action", total >= 1 and all(r["action"] == "snapshot_viewed" for r in rows))
check("actor filter matches the signed-in user", all(r["actor"] == "admin" for r in acc.search_audit(actor="admin", limit=200)[0]))

page1 = admin.get("/api/audit/search?limit=2&offset=0").get_json()
page2 = admin.get("/api/audit/search?limit=2&offset=2").get_json()
check("paging returns the total and disjoint pages",
      page1["total"] >= 5 and len(page1["entries"]) == 2 and len(page2["entries"]) == 2
      and {e["id"] for e in page1["entries"]}.isdisjoint({e["id"] for e in page2["entries"]}),
      page1["total"])

today = date.today().isoformat()
yesterday = (date.today() - timedelta(days=1)).isoformat()
check("today's date filter includes today's entries", admin.get(f"/api/audit/search?start={today}&end={today}").get_json()["total"] >= 1)
check("an end date before the entries returns none",
      admin.get(f"/api/audit/search?end={yesterday}").get_json()["total"] == 0)
check("a bad date is refused", admin.get("/api/audit/search?start=2026-13-40").status_code == 400)
check("an end date before the start is refused", admin.get(f"/api/audit/search?start={today}&end={yesterday}").status_code == 400)

actions = admin.get("/api/audit/actions").get_json()
check("action list includes the recorded actions", {"settings_changed", "snapshot_viewed", "zones_updated"} <= set(actions))

# --- 7. Export ---
exp = admin.get("/api/audit/export.csv")
check("audit export returns CSV", exp.status_code == 200 and exp.mimetype == "text/csv", exp.status_code)
text = exp.get_data(as_text=True).lstrip("\ufeff")
export_rows = list(csv.reader(io.StringIO(text)))
check("export has a header and one row per entry",
      export_rows[0][:4] == ["Entry ID", "Recorded at", "User", "Action"] and len(export_rows) - 1 >= 10, len(export_rows))
check("export is recorded in the audit log", latest("audit_exported") is not None, latest("audit_exported"))
check("export includes the masked camera source, never the password",
      "TopSecret123" not in text and "***@" in text)

passed = sum(1 for _, ok in results if ok)
print(f"\n{passed}/{len(results)} checks passed")
