import json
import os
import sqlite3
import sys
import tempfile
import types

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

tmp = tempfile.mkdtemp(prefix="vt3_")
settings_path = os.path.join(tmp, "settings.json")
db_path = os.path.join(tmp, "vigitrack.db")

# Legacy settings file: the old single admin account, with a plaintext password
with open(settings_path, "w", encoding="utf-8") as f:
    json.dump({"admin_username": "boss", "admin_password": "oldpass123"}, f)

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
        self.camera_name = s.get("camera_name", "BUILT-IN WEBCAM")
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

# --- 1. Migration of the legacy admin account ---
s = settings_store.load_settings()
check("legacy admin keys removed from settings.json",
      not any(k in s for k in ("admin_username", "admin_password", "admin_password_hash")), list(s.keys()))
c = app.test_client()
r = c.post("/api/login", json={"username": "boss", "password": "oldpass123"})
check("legacy admin logs in with old password", r.status_code == 200 and r.get_json()["user"]["role"] == "admin")
c.post("/api/logout")

# --- 2. Unauthenticated access ---
anon = app.test_client()
check("unauthenticated API returns 401", anon.get("/api/incidents").status_code == 401)
check("unauthenticated settings returns 401", anon.get("/api/settings").status_code == 401)
check("unauthenticated video feed returns 401", anon.get("/video_feed").status_code == 401)
check("old landing route removed", anon.get("/dashboard").status_code == 404)

# --- 3. Login errors and lockout ---
bad = app.test_client()
r = bad.post("/api/login", json={"username": "boss", "password": "wrong"})
check("wrong password rejected", r.status_code == 401 and "Invalid" in r.get_json()["message"])
r = bad.post("/api/login", json={"username": "nobody", "password": "x"})
check("unknown user gets the same generic message", r.status_code == 401 and r.get_json()["message"] == "Invalid username or password.")
r = bad.post("/api/login", data="a=1", content_type="text/plain")
check("login rejects non-JSON", r.status_code == 415)

lock = app.test_client()
for _ in range(4):
    lock.post("/api/login", json={"username": "boss", "password": "nope"})
r = lock.post("/api/login", json={"username": "boss", "password": "nope"})
check("fifth failure locks the account", r.status_code == 401)
r = lock.post("/api/login", json={"username": "boss", "password": "oldpass123"})
check("correct password refused while locked", r.status_code == 401 and "locked" in r.get_json()["message"].lower(), r.get_json()["message"])
boss_row = sqlite3.connect(db_path).execute("SELECT id FROM users WHERE username='boss'").fetchone()
accounts.unlock_user(boss_row[0])
r = app.test_client().post("/api/login", json={"username": "boss", "password": "oldpass123"})
check("unlock restores login", r.status_code == 200)

# --- 4. Admin creates operator accounts ---
admin = app.test_client()
admin.post("/api/login", json={"username": "boss", "password": "oldpass123"})
r = admin.post("/api/users", json={"username": "guard1", "password": "guardpass1", "role": "operator"})
check("admin creates operator", r.status_code == 201 and r.get_json()["user"]["role"] == "operator", r.get_json())
guard_id = r.get_json()["user"]["id"]
r = admin.post("/api/users", json={"username": "GUARD1", "password": "guardpass1", "role": "operator"})
check("duplicate username (case-insensitive) rejected", r.status_code == 400, r.get_json())
r = admin.post("/api/users", json={"username": "ab", "password": "guardpass1", "role": "operator"})
check("short username rejected", r.status_code == 400)
r = admin.post("/api/users", json={"username": "guard2", "password": "short", "role": "operator"})
check("short password rejected", r.status_code == 400)
r = admin.post("/api/users", json={"username": "guard2", "password": "guardpass1", "role": "superuser"})
check("invalid role rejected", r.status_code == 400)

# --- 5. Operator permissions ---
op = app.test_client()
r = op.post("/api/login", json={"username": "guard1", "password": "guardpass1"})
check("operator logs in", r.status_code == 200)
check("operator blocked until temporary password changed", op.get("/api/incidents").status_code == 403)
r = op.post("/api/me/password", json={"current_password": "guardpass1", "new_password": "guardpass1"})
check("operator completes required password change", r.status_code == 200)
check("operator reads incidents", op.get("/api/incidents").status_code == 200)
check("operator reads settings", op.get("/api/settings").status_code == 200)
me = op.get("/api/me").get_json()
check("operator /api/me reports role", me["role"] == "operator" and me["username"] == "guard1")
check("operator cannot change settings", op.post("/api/settings", json={"distance_threshold": 200, "time_threshold": 10}).status_code == 403)
check("operator cannot delete incident", op.delete("/api/incidents/1").status_code == 403)
check("operator cannot clear incidents", op.post("/api/incidents/clear").status_code == 403)
check("operator cannot list users", op.get("/api/users").status_code == 403)
check("operator cannot read audit log", op.get("/api/audit").status_code == 403)
check("operator cannot create users", op.post("/api/users", json={"username": "x1x1x", "password": "guardpass1", "role": "admin"}).status_code == 403)

# --- 6. Own password change ---
r = op.post("/api/me/password", json={"current_password": "wrongwrong", "new_password": "newpass123"})
check("own password change needs current password", r.status_code == 403)
r = op.post("/api/me/password", json={"current_password": "guardpass1", "new_password": "newpass123"})
check("own password change succeeds", r.status_code == 200)
check("old password no longer works", app.test_client().post("/api/login", json={"username": "guard1", "password": "guardpass1"}).status_code == 401)
check("new password works", app.test_client().post("/api/login", json={"username": "guard1", "password": "newpass123"}).status_code == 200)

# --- 7. Admin resets password, unlocks, disables ---
r = admin.patch(f"/api/users/{guard_id}", json={"new_password": "resetpass1"})
check("admin resets operator password", r.status_code == 200)
check("reset password works", app.test_client().post("/api/login", json={"username": "guard1", "password": "resetpass1"}).status_code == 200)

for _ in range(5):
    app.test_client().post("/api/login", json={"username": "guard1", "password": "bad"})
check("operator locked by failed attempts", app.test_client().post("/api/login", json={"username": "guard1", "password": "resetpass1"}).status_code == 401)
r = admin.patch(f"/api/users/{guard_id}", json={"unlock": True})
check("admin unlocks operator", app.test_client().post("/api/login", json={"username": "guard1", "password": "resetpass1"}).status_code == 200)

r = admin.patch(f"/api/users/{guard_id}", json={"is_active": False})
check("admin disables operator", r.status_code == 200)
check("disabled operator cannot log in", app.test_client().post("/api/login", json={"username": "guard1", "password": "resetpass1"}).status_code == 401)
check("disabled operator's session ends", op.get("/api/incidents").status_code == 401)
admin.patch(f"/api/users/{guard_id}", json={"is_active": True})
check("admin re-enables operator", app.test_client().post("/api/login", json={"username": "guard1", "password": "resetpass1"}).status_code == 200)

# --- 8. Promote and demote, with guard rails ---
r = admin.patch(f"/api/users/{guard_id}", json={"role": "admin"})
check("admin promotes operator to admin", r.status_code == 200 and r.get_json()["user"]["role"] == "admin")
r = admin.patch(f"/api/users/{guard_id}", json={"role": "operator"})
check("admin demotes operator back", r.status_code == 200)

boss_id = boss_row[0]
r = admin.patch(f"/api/users/{boss_id}", json={"is_active": False})
check("cannot disable own account", r.status_code == 400)
r = admin.patch(f"/api/users/{boss_id}", json={"role": "operator"})
check("cannot demote own account", r.status_code == 400)
r = admin.delete(f"/api/users/{boss_id}")
check("cannot delete own account", r.status_code == 400)

# last active admin protection (called directly, since self-protection blocks it via the API)
err = accounts.update_user(boss_id, role="operator")
check("last active admin cannot be demoted", err is not None and "at least one" in err.lower(), err)
err = accounts.delete_user(boss_id)
check("last active admin cannot be deleted", err is not None and "at least one" in err.lower(), err)

# --- 9. Deleting an operator ---
r = admin.delete(f"/api/users/{guard_id}")
check("admin deletes operator", r.status_code == 200)
check("deleted operator cannot log in", app.test_client().post("/api/login", json={"username": "guard1", "password": "resetpass1"}).status_code == 401)

# --- 10. Settings and audit ---
r = admin.get("/api/settings")
check("settings no longer expose admin username", "admin_username" not in r.get_json())
r = admin.post("/api/settings", json={"distance_threshold": 180, "time_threshold": 12, "admin_password": "hacked123"})
check("settings save works", r.status_code == 200)
check("admin password not changed via settings", app.test_client().post("/api/login", json={"username": "boss", "password": "oldpass123"}).status_code == 200)

audit = admin.get("/api/audit").get_json()
actions = [a["action"] for a in audit]
for expected in ("login", "login_failed", "login_blocked", "user_created", "password_changed", "password_reset",
                 "user_disabled", "user_enabled", "user_unlocked", "role_changed", "user_deleted", "settings_changed"):
    check(f"audit records {expected}", expected in actions)

passed = sum(1 for _, ok in results if ok)
print(f"\n{passed}/{len(results)} checks passed")

