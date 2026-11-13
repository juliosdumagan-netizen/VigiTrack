"""
Phase 2 checks: credential encryption, retention, date-range deletion, login rate limit,
security headers, privacy notice, and the tamper-evident audit log.
Uses temporary data and a stubbed camera. Run from the backend folder:
    python tests/test_phase2.py
"""
import json
import os
import sys
import tempfile
import types
from datetime import datetime, timedelta

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

tmp = tempfile.mkdtemp(prefix="vt_p2_")
settings_path = os.path.join(tmp, "settings.json")
db_path = os.path.join(tmp, "vigitrack.db")

from config import settings_store  # noqa: E402
from app.database import db as db_mod  # noqa: E402
settings_store.SETTINGS_PATH = settings_path
db_mod.DB_PATH = db_path

from config import secret_store  # noqa: E402


class FakeNotifier:
    audio_enabled = True

    def set_audio_enabled(self, v):
        self.audio_enabled = v


class FakeCameraManager:
    def __init__(self, *a, **k):
        self.notifier = FakeNotifier()
        self.source = 0

    def start(self):
        pass

    def get_thresholds(self):
        return {"distance_threshold": 150, "time_threshold": 10, "camera_source": secret_store.redact(self.source),
                "camera_name": "TEST CAM", "audio_alert_enabled": True, "monitored_classes": ["person"]}

    def update_thresholds(self, d, t):
        pass

    def switch_source(self, new, name=None):
        if new == "bad":
            raise RuntimeError("Camera source 'bad' could not be opened or is not responding.")
        self.source = new

    def get_recent_alerts(self):
        return []

    def get_camera_status(self):
        return {"status": "online", "last_frame_age": 0.1, "camera_name": "TEST CAM", "source": 0}

    def set_monitored_classes(self, names):
        pass


stub = types.ModuleType("app.stream.camera_manager")
stub.CameraManager = FakeCameraManager
sys.modules["app.stream.camera_manager"] = stub

import run  # noqa: E402
from app.database import users as accounts  # noqa: E402
from app.database.models import log_incident  # noqa: E402
from app.database.retention import purge_older_than  # noqa: E402
from app.database.db import get_connection  # noqa: E402
from app.stream import routes  # noqa: E402
from app.stream.rate_limit import FailureLimiter  # noqa: E402

results = []


def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))


# --- 1. Camera credentials ---
URL = "rtsp://viewer:S3cretPass@192.168.1.20:554/stream1"
token = secret_store.encrypt_source(URL)
check("encrypted token does not contain the password", "S3cretPass" not in token)
check("DPAPI round trip returns the original URL", secret_store.decrypt_source(token) == URL)
check("redact masks credentials", secret_store.redact(URL) == "rtsp://***@192.168.1.20:554/stream1")
check("redact leaves a webcam index alone", secret_store.redact(1) == 1)

settings = settings_store.load_settings()
secret_store.store_camera_source(settings, URL)
settings_store.save_settings(settings)
on_disk = open(settings_path, encoding="utf-8").read()
check("settings file has no plain-text camera password", "S3cretPass" not in on_disk and "viewer:" not in on_disk)
check("settings file keeps a masked source for display", "rtsp://***@192.168.1.20" in on_disk)
check("camera code gets the real URL back", secret_store.stored_camera_source(settings_store.load_settings()) == URL)

settings = settings_store.load_settings()
secret_store.store_camera_source(settings, 1)
check("switching to a webcam index clears the stored URL",
      "camera_source_secret" not in settings and settings["camera_source"] == 1)
settings_store.save_settings(settings)

# --- App setup ---
app = run.create_app()
accounts.create_user("boss", "bosspass1", "admin")
accounts.create_user("guard", "guardpass1", "operator")
admin = app.test_client()
admin.post("/api/login", json={"username": "boss", "password": "bosspass1"})
operator = app.test_client()
operator.post("/api/login", json={"username": "guard", "password": "guardpass1"})
anon = app.test_client()

# --- 2. Retention ---
old_bytes = b"\xff\xd8old-snapshot"
new_bytes = b"\xff\xd8new-snapshot"
old_id = log_incident("handbag", 1, 2, 180, "TEST CAM", old_bytes, [], 150, 10)
new_id = log_incident("backpack", 3, 4, 170, "TEST CAM", new_bytes, [], 150, 10)
old_time = (datetime.now() - timedelta(days=40)).isoformat(timespec="seconds")
conn = get_connection()
conn.execute("UPDATE incidents SET detected_at = ? WHERE id = ?", (old_time, old_id))
conn.commit()
conn.close()

old_file = os.path.join(db_mod.os.path.dirname(db_path), "incidents", f"{old_id}.jpg")
new_file = os.path.join(db_mod.os.path.dirname(db_path), "incidents", f"{new_id}.jpg")
check("both snapshots were saved", os.path.exists(old_file) and os.path.exists(new_file))

removed = purge_older_than(30)
check("retention removes incidents older than 30 days", removed == 1, removed)
check("retention removes the old snapshot file", not os.path.exists(old_file))
check("retention keeps recent incidents and snapshots",
      admin.get(f"/api/incidents/{new_id}").status_code == 200 and os.path.exists(new_file))
check("retention run is recorded in the audit log",
      any(a["action"] == "retention_purged" for a in admin.get("/api/audit").get_json()))

# --- 3. Retention setting ---
r = admin.post("/api/settings", json={"retention_days": 0})
check("retention of 0 days is refused", r.status_code == 400, r.get_json())
r = admin.post("/api/settings", json={"retention_days": 5000})
check("retention above 3650 days is refused", r.status_code == 400)
r = admin.post("/api/settings", json={"retention_days": "soon"})
check("non-numeric retention is refused", r.status_code == 400)
r = admin.post("/api/settings", json={"retention_days": 14})
check("admin sets retention to 14 days", r.status_code == 200)
check("settings show the retention period", admin.get("/api/settings").get_json()["retention_days"] == 14)
check("privacy notice shows the retention period (public)", anon.get("/api/notice").get_json()["retention_days"] == 14)
r = operator.post("/api/settings", json={"retention_days": 7})
check("operator cannot change retention", r.status_code == 403)

# --- 4. Delete a date range ---
today = datetime.now().date().isoformat()
r = operator.post("/api/incidents/purge", json={"start": today, "end": today})
check("operator cannot delete a date range", r.status_code == 403)
r = admin.post("/api/incidents/purge", json={"start": "2026-13-01", "end": today})
check("bad date is refused", r.status_code == 400)
r = admin.post("/api/incidents/purge", json={"start": today, "end": "2000-01-01"})
check("end before start is refused", r.status_code == 400)
r = admin.post("/api/incidents/purge", json={"start": today, "end": today})
check("admin deletes a date range", r.status_code == 200 and r.get_json()["deleted"] == 1, r.get_json())
check("range delete removes the snapshot", not os.path.exists(new_file))
check("range delete is recorded in the audit log",
      any(a["action"] == "incidents_purged" for a in admin.get("/api/audit").get_json()))

# --- 5. Security headers ---
r = anon.get("/api/notice")
csp = r.headers.get("Content-Security-Policy", "")
check("Content-Security-Policy is set", "default-src 'self'" in csp and "frame-ancestors 'none'" in csp)
check("nosniff header is set", r.headers.get("X-Content-Type-Options") == "nosniff")
check("clickjacking header is set", r.headers.get("X-Frame-Options") == "DENY")
check("referrer policy is set", r.headers.get("Referrer-Policy") == "same-origin")

# --- 6. Per-address login limit (unit) ---
now = [0.0]
limiter = FailureLimiter(max_failures=3, window_seconds=60, clock=lambda: now[0])
for _ in range(3):
    limiter.record_failure("10.0.0.5")
check("address blocked after the limit", limiter.is_blocked("10.0.0.5"))
check("other addresses are not affected", not limiter.is_blocked("10.0.0.6"))
now[0] = 59.0
check("still blocked just before the window ends", limiter.is_blocked("10.0.0.5"))
now[0] = 61.0
check("unblocked after the window", not limiter.is_blocked("10.0.0.5"))

# --- 7. Per-address login limit (route) ---
routes.login_limiter.reset()
guess = app.test_client()
statuses = [guess.post("/api/login", json={"username": f"nobody{i}", "password": "wrong"}).status_code for i in range(10)]
check("ten wrong sign-ins across accounts are each refused with 401", all(s == 401 for s in statuses), statuses)
r = guess.post("/api/login", json={"username": "boss", "password": "bosspass1"})
check("further sign-ins from that address are throttled, even with the right password",
      r.status_code == 429, r.status_code)
routes.login_limiter.reset()
r = guess.post("/api/login", json={"username": "boss", "password": "bosspass1"})
check("sign-in works again after the limit is cleared", r.status_code == 200)

# --- 8. Tamper-evident audit log ---
ok, bad, unhashed = accounts.verify_audit_chain()
check("untouched audit log verifies", ok is True, f"unhashed={unhashed}")

conn = get_connection()
middle_row = conn.execute("SELECT id, detail FROM audit_log WHERE entry_hash IS NOT NULL ORDER BY id LIMIT 1 OFFSET 3").fetchone()
middle, original_detail = middle_row["id"], middle_row["detail"]
conn.execute("UPDATE audit_log SET detail = 'nothing to see' WHERE id = ?", (middle,))
conn.commit()
ok, bad, _ = accounts.verify_audit_chain()
check("an edited entry is detected", ok is False and bad == middle, f"first bad id={bad}, edited={middle}")

r = admin.get("/api/audit/verify")
check("verify endpoint reports the broken chain", r.status_code == 200 and r.get_json()["ok"] is False)

conn.execute("UPDATE audit_log SET detail = ? WHERE id = ?", (original_detail, middle))
conn.commit()
ok, _, _ = accounts.verify_audit_chain()
check("restoring the original text makes the chain verify again", ok is True)

conn.execute("DELETE FROM audit_log WHERE id = ?", (middle,))
conn.commit()
conn.close()
ok, bad, _ = accounts.verify_audit_chain()
check("a deleted entry is detected", ok is False and bad is not None)

passed = sum(results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
