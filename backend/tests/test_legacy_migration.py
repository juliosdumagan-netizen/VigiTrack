"""
Checks the upgrade path from the single-admin settings file, plus login, secret key and
settings-route protection. Uses temporary data, so it never touches backend/data.
Run from the backend folder:  python tests/test_legacy_migration.py
"""
import json
import os
import sys
import tempfile
import types

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

tmp = tempfile.mkdtemp(prefix="vt_")
settings_path = os.path.join(tmp, "settings.json")
db_path = os.path.join(tmp, "vigitrack.db")

# Stub the heavy detection/camera stack, so the test does not need the camera or the model
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
        self.source = s.get("camera_source", 0)
        self.camera_name = s.get("camera_name", "BUILT-IN WEBCAM")
        self.notifier = FakeNotifier()
        self.distance = s.get("distance_threshold", 150)
        self.time = s.get("time_threshold", 10)

    def start(self):
        pass

    def get_thresholds(self):
        return {"distance_threshold": self.distance, "time_threshold": self.time,
                "camera_source": self.source, "camera_name": self.camera_name,
                "audio_alert_enabled": self.notifier.audio_enabled}

    def update_thresholds(self, d, t):
        self.distance, self.time = d, t
        s = settings_store.load_settings()
        s["distance_threshold"], s["time_threshold"] = d, t
        settings_store.save_settings(s)

    def switch_source(self, new, name=None):
        if new == "bad":
            raise RuntimeError("Camera source 'bad' could not be opened or is not responding.")
        self.source = new
        s = settings_store.load_settings()
        s["camera_source"] = new
        settings_store.save_settings(s)


stub = types.ModuleType("app.stream.camera_manager")
stub.CameraManager = FakeCameraManager
sys.modules["app.stream.camera_manager"] = stub

import run  # noqa: E402
from werkzeug.security import check_password_hash, generate_password_hash  # noqa: E402

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))


# 1. A settings-file admin from an older install moves into the accounts table
with open(settings_path, "w", encoding="utf-8") as f:
    json.dump({"admin_username": "boss", "admin_password_hash": generate_password_hash("oldpass")}, f)

app = run.create_app()
client = app.test_client()
with open(settings_path, encoding="utf-8") as f:
    on_disk = json.load(f)
check("legacy admin keys removed from settings.json",
      "admin_password_hash" not in on_disk and "admin_username" not in on_disk)
r = client.post("/api/login", json={"username": "boss", "password": "oldpass"})
check("migrated legacy admin can log in", r.status_code == 200, r.status_code)
check("migrated legacy admin has the admin role", r.status_code == 200 and r.get_json()["user"]["role"] == "admin")

# 2. A fresh install has no default account
os.remove(settings_path)
os.remove(db_path)
fresh_app = run.create_app()
fresh = fresh_app.test_client()
check("no default admin/admin123 account on a fresh install",
      fresh.post("/api/login", json={"username": "admin", "password": "admin123"}).status_code == 401)
check("fresh install settings have no unused keys",
      "confidence_person" not in settings_store.load_settings())

# Recreate the migrated install for the remaining checks
os.remove(db_path)
with open(settings_path, "w", encoding="utf-8") as f:
    json.dump({"admin_username": "boss", "admin_password_hash": generate_password_hash("oldpass")}, f)
app = run.create_app()
client = app.test_client()
client.post("/api/login", json={"username": "boss", "password": "oldpass"})

# 3. Secret key and cookie settings
app1 = run.create_app()
app2 = run.create_app()
check("secret key stable across starts", app1.config["SECRET_KEY"] and
      app1.config["SECRET_KEY"] == app2.config["SECRET_KEY"])
check("no hardcoded secret", app1.config["SECRET_KEY"] != "vigitrack-secure-key")
check("cookie hardening set", app1.config["SESSION_COOKIE_SAMESITE"] == "Lax" and app1.config["SESSION_COOKIE_HTTPONLY"])

# 4. Login checks
r = client.post("/api/login", data="username=boss&password=oldpass", content_type="text/plain")
check("login rejects non-JSON (CSRF-style) POST", r.status_code == 415, r.status_code)
r = client.post("/api/login", json={"username": "boss", "password": "wrong"})
check("wrong password rejected", r.status_code == 401)
r = client.post("/api/login", json={"username": "nobody", "password": "oldpass"})
check("wrong username rejected", r.status_code == 401)

# 5. Settings protection
anon = app.test_client()
r = anon.post("/api/settings", json={"distance_threshold": 200, "time_threshold": 12})
check("settings POST requires login", r.status_code == 401)
r = client.post("/api/settings", data="x=1", content_type="text/plain")
check("settings POST rejects non-JSON", r.status_code == 415, r.status_code)

# 6. Password changes go through My account, not the settings route
r = client.post("/api/settings", json={"admin_password": "hijacked1", "current_password": "oldpass"})
check("settings route ignores password fields", r.status_code == 200, r.status_code)
check("password unchanged after settings route call",
      app.test_client().post("/api/login", json={"username": "boss", "password": "oldpass"}).status_code == 200)

# 7. Partial save: failed camera switch must not save other fields
r = client.post("/api/settings", json={"distance_threshold": 300, "time_threshold": 20, "camera_source": "bad"})
check("camera switch failure returns 400", r.status_code == 400, r.get_json())
s = settings_store.load_settings()
check("no partial save on camera failure", s["distance_threshold"] == 150 and s["time_threshold"] == 10)

# 8. Successful combined update, including camera source (must not be reverted)
r = client.post("/api/settings", json={"distance_threshold": 180, "time_threshold": 15, "camera_source": 1})
check("valid update succeeds", r.status_code == 200, r.get_json())
s = settings_store.load_settings()
check("thresholds saved", s["distance_threshold"] == 180 and s["time_threshold"] == 15)
check("camera source not reverted by later save", s["camera_source"] == 1, s["camera_source"])

# 9. Bad numeric input is rejected cleanly
r = client.post("/api/settings", json={"distance_threshold": "abc", "time_threshold": 5})
check("non-numeric threshold gives 400", r.status_code == 400, r.get_json())

passed = sum(1 for _, ok in results if ok)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
