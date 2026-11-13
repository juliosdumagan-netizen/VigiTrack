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
        self.camera_name = "BUILT-IN WEBCAM"
        self.notifier = FakeNotifier()
    def start(self):
        pass
    def get_thresholds(self):
        return {"distance_threshold": 150, "time_threshold": 10, "camera_source": 0,
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

import run  # noqa: E402
from app.database import users as accounts  # noqa: E402

app = run.create_app()
c = app.test_client()

# --- 1. Fresh install ---
check("fresh install needs setup", c.get("/api/setup/status").get_json()["setup_required"] is True)
code = accounts._setup_state["code"]
check("setup code generated", code is not None and len(code) == 11, code)
check("default admin/admin123 does not exist", c.post("/api/login", json={"username": "admin", "password": "admin123"}).status_code == 401)
check("protected API still requires login", c.get("/api/incidents").status_code == 401)
check("settings.json has no admin password", "admin_password_hash" not in settings_store.load_settings())

# --- 2. Setup code checks ---
r = c.post("/api/setup", json={"setup_code": "000-000-000", "username": "owner", "password": "ownerpass1"})
check("wrong setup code refused", r.status_code == 403, r.get_json())
r = c.post("/api/setup", json={"setup_code": code, "username": "owner", "password": "short"})
check("correct code but weak password refused", r.status_code == 400)
r = c.post("/api/setup", json={"setup_code": code, "username": "x", "password": "ownerpass1"})
check("correct code but bad username refused", r.status_code == 400)

for _ in range(4):
    c.post("/api/setup", json={"setup_code": "111-111-111", "username": "owner", "password": "ownerpass1"})
r = c.post("/api/setup", json={"setup_code": code, "username": "owner", "password": "ownerpass1"})
check("setup locks after too many wrong codes", r.status_code == 403 and "Too many" in r.get_json()["message"], r.get_json())

# restarting regenerates the code
new_code = accounts.prepare_first_run()
check("restart issues a new code", new_code is not None and new_code != code)

# --- 3. Successful setup ---
owner = app.test_client()
r = owner.post("/api/setup", json={"setup_code": new_code, "username": "owner", "password": "ownerpass1"})
check("setup creates admin", r.status_code == 201 and r.get_json()["user"]["role"] == "admin", r.get_json())
check("setup admin is logged in", owner.get("/api/me").status_code == 200)
check("setup admin is not forced to change password", owner.get("/api/me").get_json()["must_change_password"] is False)
check("setup status now closed", c.get("/api/setup/status").get_json()["setup_required"] is False)
r = c.post("/api/setup", json={"setup_code": new_code, "username": "intruder", "password": "intruder1"})
check("setup cannot run twice", r.status_code == 400 and "already" in r.get_json()["message"])
check("prepare_first_run does nothing after setup", accounts.prepare_first_run() is None)
check("owner can log in later", app.test_client().post("/api/login", json={"username": "owner", "password": "ownerpass1"}).status_code == 200)

# --- 4. Admin creates an operator with a temporary password ---
r = owner.post("/api/users", json={"username": "guard1", "password": "temppass1", "role": "operator"})
check("admin creates operator", r.status_code == 201)
guard = app.test_client()
r = guard.post("/api/login", json={"username": "guard1", "password": "temppass1"})
check("operator logs in with temporary password", r.status_code == 200 and r.get_json()["user"]["must_change_password"] is True)
check("operator blocked until password changed", guard.get("/api/incidents").status_code == 403)
check("operator blocked from settings until password changed", guard.get("/api/settings").status_code == 403)
check("operator can still read own profile", guard.get("/api/me").status_code == 200)
r = guard.post("/api/me/password", json={"current_password": "temppass1", "new_password": "guardpass1"})
check("operator sets own password", r.status_code == 200)
check("operator unlocked after changing password", guard.get("/api/incidents").status_code == 200)
check("temporary password no longer works", app.test_client().post("/api/login", json={"username": "guard1", "password": "temppass1"}).status_code == 401)

# --- 5. Admin reset also forces a change ---
guard_id = next(u["id"] for u in owner.get("/api/users").get_json() if u["username"] == "guard1")
owner.patch(f"/api/users/{guard_id}", json={"new_password": "resetpass1"})
g2 = app.test_client()
g2.post("/api/login", json={"username": "guard1", "password": "resetpass1"})
check("admin reset forces password change", g2.get("/api/incidents").status_code == 403)

# --- 6. Audit trail ---
actions = [a["action"] for a in owner.get("/api/audit").get_json()]
check("audit records setup", "setup_completed" in actions)
check("audit records setup failures", "setup_failed" in actions)

passed = sum(1 for _, ok in results if ok)
print(f"\n{passed}/{len(results)} checks passed")

