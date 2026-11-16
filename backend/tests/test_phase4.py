import csv
import io
import os
import sys
import tempfile
import types

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

tmp = tempfile.mkdtemp(prefix="vt4_")
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

# --- 1. CSV builder (pure) ---
from app.database.export import CSV_COLUMNS, incidents_to_csv

sample = [{
    "id": 1, "detected_at": "2026-11-12T23:00:00", "camera_name": "=HYPERLINK(\"x\")", "object_class": "backpack",
    "object_track_id": 4, "person_track_id": None, "distance": 180.5, "distance_threshold": 150.0,
    "time_threshold": 10.0, "status": "unattended", "review_status": "dismissed",
    "review_note": "Owner, returned \"quickly\"\nline two", "reviewed_by": "ang",
    "reviewed_at": "2026-11-12T23:05:00", "state_history": [{"state": "x"}], "image_url": "/x",
}]
raw = incidents_to_csv(sample)
check("csv starts with UTF-8 BOM", raw.startswith(b"\xef\xbb\xbf"))
text = raw[3:].decode("utf-8")
check("csv uses CRLF row endings", text.endswith("\r\n") and text.index("\r\n") < text.index("\n"))
rows = list(csv.reader(io.StringIO(text)))
check("csv header row matches column list", rows[0] == [label for _, label in CSV_COLUMNS], rows[0])
check("csv data row has one cell per column", len(rows[1]) == len(CSV_COLUMNS) == len(rows[0]), len(rows[1]))
data = dict(zip([k for k, _ in CSV_COLUMNS], rows[1]))
check("formula-like camera name is neutralised", data["camera_name"] == "'=HYPERLINK(\"x\")", data["camera_name"])
check("quotes, commas and newlines round-trip", data["review_note"] == "Owner, returned \"quickly\"\nline two", data["review_note"])
check("missing values are empty cells", data["person_track_id"] == "", data["person_track_id"])
check("timeline and snapshot are not exported", "state_history" not in rows[0] and "image_url" not in rows[0])

# --- 2. Endpoint ---
import run  # noqa: E402  (also runs init_db via create_app)
app = run.create_app()
client = app.test_client()

from app.database.models import log_incident
from app.database import users as _acc

anon = app.test_client()
check("export requires login", anon.get("/api/incidents/export.csv").status_code == 401)

_code = _acc._setup_state["code"] or _acc.prepare_first_run()
client.post("/api/setup", json={"setup_code": _code, "username": "admin", "password": "admin123"})

# More rows than the hub list shows (100), to prove the export is not capped.
for i in range(105):
    log_incident("backpack", 1000 + i, None, 120.0, "BUILT-IN WEBCAM")

resp = client.get("/api/incidents/export.csv")
check("export returns 200 for a signed-in user", resp.status_code == 200, resp.status_code)
check("export is served as text/csv", resp.mimetype == "text/csv", resp.mimetype)
disposition = resp.headers.get("Content-Disposition", "")
check("export is an attachment with a dated filename",
      disposition.startswith('attachment; filename="vigitrack-incidents-') and disposition.endswith('.csv"'),
      disposition)
body = resp.get_data(as_text=True)
body_rows = list(csv.reader(io.StringIO(body.lstrip("\ufeff"))))
check("export includes all 105 incidents, not just the 100 shown", len(body_rows) - 1 == 105, len(body_rows) - 1)
check("export rows are oldest first", body_rows[1][0] == "1", body_rows[1][0])

audit = [row for row in _acc.list_audit() if row["action"] == "incidents_exported"]
check("export is written to the audit log", len(audit) == 1 and audit[0]["detail"] == "105 record(s) as CSV",
      audit[0]["detail"] if audit else None)

# --- 3. Single-incident PDF ---
import io as _io
from PIL import Image as _Image

_buf = _io.BytesIO()
_Image.new("RGB", (320, 240), (40, 40, 60)).save(_buf, format="JPEG")
real_jpeg = _buf.getvalue()

with_snap = log_incident("backpack", 77, 3, 140.0, "LOBBY <CAM>", image_bytes=real_jpeg,
                         state_history=[{"time": "2026-11-12T23:00:00", "state": "STATIC_ATTENDED"},
                                        {"time": "2026-11-12T23:00:12", "state": "UNATTENDED_ALERT"}],
                         distance_threshold=150, time_threshold=10)
client.post(f"/api/incidents/{with_snap}/review", json={"action": "dismissed", "note": "Owner & <b>bag</b>"})
no_snap = log_incident("suitcase", 78, None, None, "LOBBY")

check("pdf requires login", anon.get(f"/api/incidents/{with_snap}/report.pdf").status_code == 401)
check("pdf for missing incident is 404", client.get("/api/incidents/9999/report.pdf").status_code == 404)

pdf = client.get(f"/api/incidents/{with_snap}/report.pdf")
check("pdf returns 200", pdf.status_code == 200, pdf.status_code)
check("pdf is served as application/pdf", pdf.mimetype == "application/pdf", pdf.mimetype)
check("pdf is an attachment named after the incident",
      pdf.headers.get("Content-Disposition") == f'attachment; filename="vigitrack-incident-{with_snap}.pdf"',
      pdf.headers.get("Content-Disposition"))
check("pdf has a valid header and trailer", pdf.data.startswith(b"%PDF-") and b"%%EOF" in pdf.data[-64:])
check("pdf with snapshot embeds the image", len(pdf.data) > len(real_jpeg))

bare = client.get(f"/api/incidents/{no_snap}/report.pdf")
check("pdf without snapshot still builds", bare.status_code == 200 and bare.data.startswith(b"%PDF-"), bare.status_code)

audit_pdf = [row for row in _acc.list_audit() if row["action"] == "incident_report_exported"]
check("pdf export is written to the audit log",
      sorted(r["detail"] for r in audit_pdf) == sorted([f"#{with_snap}", f"#{no_snap}"]),
      [r["detail"] for r in audit_pdf])

# --- 4. Zones API ---
ZONE_DESK = {"name": "Reception desk", "type": "ignore", "points": [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4]]}
ZONE_DOOR = {"name": "Front door", "type": "watch", "time_threshold": 4, "points": [[0.7, 0.7], [0.95, 0.7], [0.95, 0.95]]}

check("zones read requires login", anon.get("/api/zones").status_code == 401)
check("zones write requires login", anon.post("/api/zones", json={"zones": []}).status_code == 401)

client.post("/api/users", json={"username": "ops", "password": "operator123", "role": "operator"})
ops = app.test_client()
ops.post("/api/login", json={"username": "ops", "password": "operator123"})
ops.post("/api/me/password", json={"current_password": "operator123", "new_password": "operator456"})
ops.post("/api/login", json={"username": "ops", "password": "operator456"})
check("operator can read zones", ops.get("/api/zones").status_code == 200)
denied = ops.post("/api/zones", json={"zones": [ZONE_DESK]})
check("operator cannot change zones", denied.status_code == 403, denied.status_code)

saved = client.post("/api/zones", json={"zones": [ZONE_DESK, ZONE_DOOR]})
check("admin saves valid zones", saved.status_code == 200 and len(saved.get_json()["zones"]) == 2, saved.status_code)
read_back = client.get("/api/zones").get_json()["zones"]
check("saved zones are returned on read", [z["name"] for z in read_back] == ["Reception desk", "Front door"])
check("watch zone keeps its time limit", read_back[1]["time_threshold"] == 4.0)

bad = client.post("/api/zones", json={"zones": [{"name": "Lonely", "type": "ignore", "points": [[0, 0]]}]})
check("invalid zones are rejected with a message", bad.status_code == 400 and "at least three points" in bad.get_json()["message"],
      bad.get_json())
check("rejected save leaves the saved zones unchanged", len(client.get("/api/zones").get_json()["zones"]) == 2)

zone_audit = [row for row in _acc.list_audit() if row["action"] == "zones_updated"]
check("zone save is written to the audit log",
      len(zone_audit) == 1 and zone_audit[0]["detail"] == "added Reception desk (ignore); added Front door (watch 4.0 s)",
      [r["detail"] for r in zone_audit])

# --- 5. Class evidence stored with each incident ---
from app.database.models import get_incident as _get_incident
evidence = {"suitcase": {"frames": 11, "max_confidence": 0.35}, "handbag": {"frames": 3, "max_confidence": 0.21}}
with_ev = log_incident("suitcase", 22, None, 150.0, "LOBBY", class_evidence=evidence)
stored_ev = _get_incident(with_ev) if with_ev is not None else None
stored_none = _get_incident(no_snap) if no_snap is not None else None
check("class evidence is stored and read back", stored_ev is not None and stored_ev["class_evidence"] == evidence)
check("incident without evidence reads as null", stored_none is not None and stored_none["class_evidence"] is None)

passed = sum(1 for _, ok in results if ok)
print(f"\n{passed}/{len(results)} checks passed")
