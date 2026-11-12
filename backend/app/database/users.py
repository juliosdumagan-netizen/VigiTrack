import hmac
import os
import re
import secrets
import threading
from datetime import datetime, timedelta
from typing import Optional, Tuple

from werkzeug.security import check_password_hash, generate_password_hash

from app.database.db import get_connection
from config.settings_store import load_settings, save_settings

ROLES = ("admin", "operator")
LOCKOUT_THRESHOLD = 5
LOCKOUT_MINUTES = 15
MIN_PASSWORD_LENGTH = 8
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
SETUP_MAX_FAILURES = 5

# Desktop mode: the server only listens on this PC, so the setup code is not needed.
DESKTOP_MODE = os.getenv("VIGITRACK_DESKTOP") == "1"

_setup_lock = threading.Lock()
_setup_state = {"code": None, "failed": 0}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def public_user(row) -> Optional[dict]:
    """Converts a users row to a dict that is safe to send to the browser."""
    if row is None:
        return None
    locked_until = row["locked_until"]
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "is_locked": bool(locked_until and locked_until > _now()),
        "failed_attempts": row["failed_attempts"],
        "created_at": row["created_at"],
        "last_login_at": row["last_login_at"],
        "must_change_password": bool(row["must_change_password"]),
    }


def validate_username(username: str) -> Optional[str]:
    if not USERNAME_PATTERN.match(username or ""):
        return "Username must be 3–32 characters: letters, numbers, dot, dash or underscore."
    return None


def validate_password(password: str) -> Optional[str]:
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return None


def log_audit(actor: Optional[str], action: str, detail: Optional[str] = None) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO audit_log (created_at, actor, action, detail) VALUES (?, ?, ?, ?)",
            (_now(), actor, action, detail),
        )
        conn.commit()
    except Exception as e:
        print(f"[Audit Error] Could not record '{action}': {e}")
    finally:
        conn.close()


def list_audit(limit: int = 200) -> list:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, created_at, actor, action, detail FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def setup_required() -> bool:
    """True when no accounts exist yet, so the first-run setup must be completed."""
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    finally:
        conn.close()


def setup_code_required() -> bool:
    return not DESKTOP_MODE


def prepare_first_run() -> Optional[str]:
    """
    Called at startup. If accounts already exist, does nothing.
    If an install from before the setup screen is found (admin stored in settings.json),
    that admin is moved into the users table so its password keeps working.
    Otherwise a one-time setup code is generated and printed to the terminal.
    Returns the setup code, or None.
    """
    if not setup_required():
        return None

    settings = load_settings()
    if settings.get("admin_password_hash"):
        username = settings.get("admin_username", "admin")
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
                (username, settings["admin_password_hash"], _now()),
            )
            conn.commit()
        finally:
            conn.close()
        for key in ("admin_username", "admin_password_hash", "admin_password"):
            settings.pop(key, None)
        save_settings(settings)
        log_audit(None, "legacy_admin_migrated", username)
        return None

    if DESKTOP_MODE:
        with _setup_lock:
            _setup_state["code"] = ""
            _setup_state["failed"] = 0
        return None

    code = "-".join(f"{secrets.randbelow(1000):03d}" for _ in range(3))
    with _setup_lock:
        _setup_state["code"] = code
        _setup_state["failed"] = 0
    print("=" * 65)
    print("  FIRST-RUN SETUP")
    print("  No accounts exist yet. Open the VigiTrack setup page and")
    print("  enter this code to create the administrator account:")
    print(f"      Setup code: {code}")
    print("  The code is valid until the admin account is created.")
    print("=" * 65)
    return code


def complete_setup(code: str, username: str, password: str) -> Tuple[Optional[dict], Optional[str]]:
    """Creates the first administrator account if the setup code is correct."""
    with _setup_lock:
        if not setup_required():
            return None, "Setup has already been completed."
        if _setup_state["code"] is None:
            return None, "Setup is not available. Restart the backend to get a new setup code."
        if _setup_state["failed"] >= SETUP_MAX_FAILURES:
            return None, "Too many incorrect setup codes. Restart the backend to get a new code."

        if setup_code_required() and not hmac.compare_digest(
            code.strip().encode("utf-8"), _setup_state["code"].encode("utf-8")
        ):
            _setup_state["failed"] += 1
            log_audit(None, "setup_failed", "wrong setup code")
            return None, "Setup code is incorrect."

        user, error = create_user(username, password, "admin")
        if error:
            return None, error

        _setup_state["code"] = None
        log_audit(user["username"], "setup_completed")
        return user, None


def get_user_by_username(username: str) -> Optional[dict]:
    conn = get_connection()
    try:
        return public_user(conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone())
    finally:
        conn.close()


def get_user(user_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        return public_user(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
    finally:
        conn.close()


def list_users() -> list:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM users ORDER BY username COLLATE NOCASE").fetchall()
        return [public_user(r) for r in rows]
    finally:
        conn.close()


def count_active_admins(conn=None) -> int:
    own = conn is None
    conn = conn or get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1"
        ).fetchone()[0]
    finally:
        if own:
            conn.close()


def create_user(username: str, password: str, role: str, must_change: bool = False) -> Tuple[Optional[dict], Optional[str]]:
    if role not in ROLES:
        return None, "Role must be admin or operator."
    error = validate_username(username) or validate_password(password)
    if error:
        return None, error
    conn = get_connection()
    try:
        exists = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if exists:
            return None, "That username is already taken."
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at, must_change_password) VALUES (?, ?, ?, ?, ?)",
            (username, generate_password_hash(password), role, _now(), int(must_change)),
        )
        conn.commit()
        user_id = cursor.lastrowid
    finally:
        conn.close()
    return get_user(user_id), None


def update_user(user_id: int, role: Optional[str] = None, is_active: Optional[bool] = None) -> Optional[str]:
    conn = get_connection()
    try:
        target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if target is None:
            return "User not found."
        new_role = role or target["role"]
        new_active = target["is_active"] if is_active is None else int(bool(is_active))
        if new_role not in ROLES:
            return "Role must be admin or operator."
        losing_admin = target["role"] == "admin" and target["is_active"] and not (new_role == "admin" and new_active)
        if losing_admin and count_active_admins(conn) <= 1:
            return "At least one active admin account is required."
        conn.execute("UPDATE users SET role = ?, is_active = ? WHERE id = ?", (new_role, new_active, user_id))
        conn.commit()
        return None
    finally:
        conn.close()


def set_password(user_id: int, password: str, must_change: bool = False) -> Optional[str]:
    error = validate_password(password)
    if error:
        return error
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL, must_change_password = ? WHERE id = ?",
            (generate_password_hash(password), int(must_change), user_id),
        )
        conn.commit()
        return None
    finally:
        conn.close()


def unlock_user(user_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def delete_user(user_id: int) -> Optional[str]:
    conn = get_connection()
    try:
        target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if target is None:
            return "User not found."
        if target["role"] == "admin" and target["is_active"] and count_active_admins(conn) <= 1:
            return "At least one active admin account is required."
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return None
    finally:
        conn.close()


def verify_password(user_id: int, password: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
        return bool(row) and check_password_hash(row["password_hash"], password)
    finally:
        conn.close()


def authenticate(username: str, password: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Checks credentials and returns (user, None) on success or (None, reason) on failure.
    reason is one of: "invalid", "locked", "disabled".
    """
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            log_audit(username or None, "login_failed", "unknown user")
            return None, "invalid"

        if row["locked_until"] and row["locked_until"] > _now():
            log_audit(row["username"], "login_blocked", "account locked")
            return None, "locked"

        if not check_password_hash(row["password_hash"], password):
            attempts = row["failed_attempts"] + 1
            locked_until = None
            if attempts >= LOCKOUT_THRESHOLD:
                locked_until = (datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat(timespec="seconds")
                attempts = 0
            conn.execute(
                "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                (attempts, locked_until, row["id"]),
            )
            conn.commit()
            log_audit(row["username"], "login_failed", "wrong password" + (" (account locked)" if locked_until else ""))
            return None, "invalid"

        if not row["is_active"]:
            log_audit(row["username"], "login_blocked", "account disabled")
            return None, "disabled"

        conn.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login_at = ? WHERE id = ?",
            (_now(), row["id"]),
        )
        conn.commit()
        log_audit(row["username"], "login")
        return get_user(row["id"]), None
    finally:
        conn.close()
