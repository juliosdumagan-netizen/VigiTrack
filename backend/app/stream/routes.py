import math
import os
import secrets
import threading
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Optional
from flask import Blueprint, Response, jsonify, request, session, redirect, send_from_directory
from werkzeug.security import check_password_hash
from app.database.retention import DEFAULT_RETENTION_DAYS, purge_between
from app.detection.classes import SUPPORTED_CLASSES
from app.stream.camera_manager import CameraManager
from app.stream.rate_limit import FailureLimiter
from app.detection.zones import ZoneError
from app.database.export import audit_to_csv, incidents_to_csv
from app.database.incident_report import incident_to_pdf
from app.database.models import (
    INCIDENT_IMAGE_DIR,
    clear_all_incidents,
    delete_incident,
    get_all_incidents,
    get_all_incidents_for_export,
    get_incident,
    get_incident_image_filename,
    review_incident,
)
from app.database import users as accounts
from config.secret_store import redact, stored_camera_source
from config.settings_store import load_settings, save_settings

stream_bp = Blueprint(
    "stream_bp",
    __name__,
    template_folder="templates"
)

# Global camera manager instance
camera_manager = None
camera_manager_lock = threading.Lock()


def get_camera_manager():
    global camera_manager
    with camera_manager_lock:
        if camera_manager is None:
            camera_manager = CameraManager()
            camera_manager.start()
    return camera_manager


IDLE_TIMEOUT_SECONDS = int(os.getenv("VIGITRACK_IDLE_MINUTES", "30")) * 60
_STREAM_CHECK_INTERVAL_SECONDS = 1.0

_session_lock = threading.Lock()
_active_sessions: Dict[str, float] = {}
_revoked_sids: Dict[str, float] = {}


def _prune_sessions(now: float) -> None:
    max_age = max(IDLE_TIMEOUT_SECONDS, 8 * 3600)
    for store in (_active_sessions, _revoked_sids):
        expired = [k for k, ts in store.items() if now - ts > max_age]
        for k in expired:
            del store[k]


def _touch_session(sid: str, now: float) -> None:
    with _session_lock:
        _prune_sessions(now)
        _active_sessions[sid] = now


def _drop_session(sid: Optional[str]) -> None:
    if not sid:
        return
    now = time.time()
    with _session_lock:
        _prune_sessions(now)
        _active_sessions.pop(sid, None)
        _revoked_sids[sid] = now


def _session_still_valid(user_id: int, sid: Optional[str]) -> bool:
    if sid is not None:
        with _session_lock:
            if sid in _revoked_sids:
                return False
            last_active = _active_sessions.get(sid)
        if last_active is None or time.time() - last_active > IDLE_TIMEOUT_SECONDS:
            return False
    user = accounts.get_user(user_id)
    return user is not None and bool(user["is_active"])


def generate_frames(user_id: Optional[int] = None, sid: Optional[str] = None):
    """Generator streaming multipart MJPEG frames to web clients."""
    cam = get_camera_manager()
    last_check = time.monotonic()
    while True:
        if user_id is not None:
            now_mono = time.monotonic()
            if now_mono - last_check >= _STREAM_CHECK_INTERVAL_SECONDS:
                last_check = now_mono
                if not _session_still_valid(user_id, sid):
                    return
        frame_bytes = cam.get_frame()
        if frame_bytes is not None:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
        time.sleep(0.03)  # ~30 FPS throttle for streaming


# Polling endpoints the hub calls in the background. They do not count as user activity,
# so a dashboard left open on its own still times out.
BACKGROUND_ENDPOINTS = {
    "stream_bp.video_feed",
    "stream_bp.api_alerts",
    "stream_bp.api_camera_status",
}


def _current_user():
    """
    Returns the logged-in user from the database, or None.
    Ends the session if the account is gone or disabled, or after the idle timeout.
    """
    user_id = session.get("user_id")
    if not user_id:
        return None
    sid = session.get("sid")
    if sid:
        with _session_lock:
            if sid in _revoked_sids:
                session.clear()
                return None

    user = accounts.get_user(user_id)
    if user is None or not user["is_active"]:
        _drop_session(sid)
        session.clear()
        return None

    now = time.time()
    last_seen = session.get("last_seen")
    if last_seen is not None and now - last_seen > IDLE_TIMEOUT_SECONDS:
        accounts.log_audit(user["username"], "session_expired", "idle timeout")
        _drop_session(sid)
        session.clear()
        return None

    if not sid:
        sid = secrets.token_hex(16)
        session["sid"] = sid

    if last_seen is None or request.endpoint not in BACKGROUND_ENDPOINTS:
        session["last_seen"] = now
        _touch_session(sid, now)
    else:
        with _session_lock:
            _active_sessions.setdefault(sid, last_seen)
    return user


def _actor() -> str:
    """Username of the signed-in user. Only used behind login_required/admin_required."""
    user = _current_user()
    assert user is not None, "login_required has already checked the session"
    return user["username"]


PASSWORD_CHANGE_ALLOWED = {
    "stream_bp.api_me",
    "stream_bp.api_change_own_password",
    "stream_bp.api_logout",
    "stream_bp.logout",
}


def login_required(f):
    """Requires any logged-in, active account that has finished any required password change."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = _current_user()
        if user is None:
            return jsonify({"status": "unauthorized", "message": "Authentication required. Please log in."}), 401
        if user["must_change_password"] and request.endpoint not in PASSWORD_CHANGE_ALLOWED:
            return jsonify({
                "status": "password_change_required",
                "message": "You must change your temporary password before continuing.",
            }), 403
        return f(*args, **kwargs)
    return decorated_function


def role_required(role):
    """Requires a logged-in account with the given role (admins always pass)."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user = _current_user()
            assert user is not None, "login_required has already checked the session"
            if user["role"] != role and user["role"] != "admin":
                return jsonify({"status": "forbidden", "message": "This action needs an administrator account."}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Requires an administrator account."""
    return role_required("admin")(f)


def _client_ip():
    return request.remote_addr or "unknown"


# Per-address limit on failed sign-ins. Stops guessing across many accounts, which the per-account lockout does not.
login_limiter = FailureLimiter(max_failures=10, window_seconds=60)


# =========================================================================
# Authentication Routes
# =========================================================================

@stream_bp.route("/api/notice", methods=["GET"])
def api_notice():
    """Public: what the privacy notice on the sign-in page should say."""
    return jsonify({"retention_days": int(load_settings().get("retention_days", DEFAULT_RETENTION_DAYS))})


@stream_bp.route("/api/login", methods=["POST"])
def api_login():
    """Validates credentials, applies lockout, and establishes a session."""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Expected a JSON request."}), 415

    if login_limiter.is_blocked(_client_ip()):
        return jsonify({
            "status": "error",
            "message": "Too many failed sign-in attempts from this computer. Wait a minute, then try again.",
        }), 429

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = str(data.get("password") or "")

    user, reason = accounts.authenticate(username, password)
    if not user:
        login_limiter.record_failure(_client_ip())
    if user:
        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        now = time.time()
        session["last_seen"] = now
        sid = secrets.token_hex(16)
        session["sid"] = sid
        _touch_session(sid, now)
        return jsonify({
            "status": "success",
            "message": "Authentication successful",
            "redirect": "/dashboard",
            "user": user,
        })

    messages = {
        "locked": "Too many failed attempts. This account is locked for 15 minutes.",
        "disabled": "This account has been disabled. Contact an administrator.",
    }
    return jsonify({
        "status": "error",
        "message": messages.get(reason or "", "Invalid username or password."),
    }), 401


@stream_bp.route("/api/setup/status", methods=["GET"])
def api_setup_status():
    return jsonify({
        "setup_required": accounts.setup_required(),
        "setup_code_required": accounts.setup_code_required(),
    })


@stream_bp.route("/api/setup", methods=["POST"])
def api_setup():
    """First-run setup: creates the administrator account, only while no accounts exist and with the setup code."""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Expected a JSON request."}), 415
    data = request.get_json(silent=True) or {}
    user, error = accounts.complete_setup(
        str(data.get("setup_code") or ""),
        str(data.get("username") or "").strip(),
        str(data.get("password") or ""),
    )
    if error:
        status = 403 if error.startswith("Setup code") or error.startswith("Too many") else 400
        return jsonify({"status": "error", "message": error}), status
    assert user is not None
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    now = time.time()
    session["last_seen"] = now
    sid = secrets.token_hex(16)
    session["sid"] = sid
    _touch_session(sid, now)
    return jsonify({"status": "success", "user": user}), 201


@stream_bp.route("/api/logout", methods=["POST"])
def api_logout():
    user = _current_user()
    if user:
        accounts.log_audit(user["username"], "logout")
    _drop_session(session.get("sid"))
    session.clear()
    return jsonify({"status": "success"})


@stream_bp.route("/logout")
def logout():
    """Ends the session and redirects back to the hub's start page."""
    user = _current_user()
    if user:
        accounts.log_audit(user["username"], "logout")
    _drop_session(session.get("sid"))
    session.clear()
    return redirect("/")


@stream_bp.route("/api/me", methods=["GET"])
@login_required
def api_me():
    return jsonify(_current_user())


@stream_bp.route("/api/me/password", methods=["POST"])
@login_required
def api_change_own_password():
    if not request.is_json:
        return jsonify({"status": "error", "message": "Expected a JSON request."}), 415
    user = _current_user()
    assert user is not None, "login_required has already checked the session"
    data = request.get_json(silent=True) or {}
    current = str(data.get("current_password") or "")
    new = str(data.get("new_password") or "")

    if not accounts.verify_password(user["id"], current):
        accounts.log_audit(user["username"], "password_change_failed", "wrong current password")
        return jsonify({"status": "error", "message": "Current password is incorrect."}), 403

    error = accounts.set_password(user["id"], new)
    if error:
        return jsonify({"status": "error", "message": error}), 400

    accounts.log_audit(user["username"], "password_changed", "own password")
    return jsonify({"status": "success"})


# =========================================================================
# User & Audit Management (Administrators only)
# =========================================================================

@stream_bp.route("/api/users", methods=["GET"])
@admin_required
def api_list_users():
    return jsonify(accounts.list_users())


@stream_bp.route("/api/users", methods=["POST"])
@admin_required
def api_create_user():
    if not request.is_json:
        return jsonify({"status": "error", "message": "Expected a JSON request."}), 415
    actor = _actor()
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    role = str(data.get("role") or "operator")

    user, error = accounts.create_user(username, password, role, must_change=True)
    if error:
        return jsonify({"status": "error", "message": error}), 400
    assert user is not None
    accounts.log_audit(actor, "user_created", f"{user['username']} ({user['role']})")
    return jsonify({"status": "success", "user": user}), 201


@stream_bp.route("/api/users/<int:user_id>", methods=["PATCH"])
@admin_required
def api_update_user(user_id):
    if not request.is_json:
        return jsonify({"status": "error", "message": "Expected a JSON request."}), 415
    actor_user = _current_user()
    assert actor_user is not None, "admin_required has already checked the session"
    data = request.get_json(silent=True) or {}
    target = accounts.get_user(user_id)
    if target is None:
        return jsonify({"status": "error", "message": "User not found."}), 404

    if "role" in data or "is_active" in data:
        if target["id"] == actor_user["id"] and data.get("is_active") is False:
            return jsonify({"status": "error", "message": "You cannot disable your own account."}), 400
        if target["id"] == actor_user["id"] and data.get("role") not in (None, "admin"):
            return jsonify({"status": "error", "message": "You cannot remove your own admin role."}), 400
        error = accounts.update_user(
            user_id,
            role=data.get("role"),
            is_active=data.get("is_active") if "is_active" in data else None,
        )
        if error:
            return jsonify({"status": "error", "message": error}), 400
        if "role" in data and data["role"] != target["role"]:
            accounts.log_audit(actor_user["username"], "role_changed", f"{target['username']}: {target['role']} → {data['role']}")
        if "is_active" in data and bool(data["is_active"]) != target["is_active"]:
            action = "user_enabled" if data["is_active"] else "user_disabled"
            accounts.log_audit(actor_user["username"], action, target["username"])

    if data.get("unlock"):
        accounts.unlock_user(user_id)
        accounts.log_audit(actor_user["username"], "user_unlocked", target["username"])

    if data.get("new_password"):
        error = accounts.set_password(user_id, str(data["new_password"]), must_change=True)
        if error:
            return jsonify({"status": "error", "message": error}), 400
        accounts.log_audit(actor_user["username"], "password_reset", target["username"])

    return jsonify({"status": "success", "user": accounts.get_user(user_id)})


@stream_bp.route("/api/users/<int:user_id>", methods=["DELETE"])
@admin_required
def api_delete_user(user_id):
    actor_user = _current_user()
    assert actor_user is not None, "admin_required has already checked the session"
    target = accounts.get_user(user_id)
    if target is None:
        return jsonify({"status": "error", "message": "User not found."}), 404
    if target["id"] == actor_user["id"]:
        return jsonify({"status": "error", "message": "You cannot delete your own account."}), 400
    error = accounts.delete_user(user_id)
    if error:
        return jsonify({"status": "error", "message": error}), 400
    accounts.log_audit(actor_user["username"], "user_deleted", target["username"])
    return jsonify({"status": "success"})


@stream_bp.route("/api/audit", methods=["GET"])
@admin_required
def api_audit_log():
    return jsonify(accounts.list_audit())


@stream_bp.route("/api/audit/verify", methods=["GET"])
@admin_required
def api_verify_audit():
    """Checks the audit log's hash chain. A failure means an entry was changed or removed."""
    ok, first_bad_id, unhashed = accounts.verify_audit_chain()
    return jsonify({"ok": ok, "first_bad_id": first_bad_id, "unhashed_entries": unhashed})


def _audit_filters():
    """Reads and checks the audit search filters from the query string. Raises ValueError on bad input."""
    def parse_date(name):
        value = (request.args.get(name) or "").strip()
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
        except ValueError:
            raise ValueError(f"{name} must be a date in the form YYYY-MM-DD.")

    start = parse_date("start")
    end = parse_date("end")
    if start and end and end < start:
        raise ValueError("The end date is before the start date.")
    return {
        "actor": (request.args.get("actor") or "").strip() or None,
        "action": (request.args.get("action") or "").strip() or None,
        "start": start,
        "end": end,
    }


@stream_bp.route("/api/audit/search", methods=["GET"])
@admin_required
def api_search_audit():
    try:
        filters = _audit_filters()
        limit = min(max(int(request.args.get("limit", 50)), 1), 200)
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    entries, total = accounts.search_audit(limit=limit, offset=offset, **filters)
    return jsonify({"entries": entries, "total": total})


@stream_bp.route("/api/audit/actions", methods=["GET"])
@admin_required
def api_audit_actions():
    return jsonify(accounts.audit_action_names())


@stream_bp.route("/api/audit/export.csv", methods=["GET"])
@admin_required
def api_export_audit_csv():
    try:
        filters = _audit_filters()
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    entries = accounts.iter_audit_for_export(**filters)
    accounts.log_audit(_actor(), "audit_exported", f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}")
    filename = f"vigitrack-audit-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    return Response(
        audit_to_csv(entries),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =========================================================================
# Protected Surveillance & Management Routes
# =========================================================================

@stream_bp.route("/video_feed")
@login_required
def video_feed():
    """Protected live MJPEG video stream."""
    return Response(
        generate_frames(user_id=session.get("user_id"), sid=session.get("sid")),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@stream_bp.route("/api/alerts")
@login_required
def api_alerts():
    cam = get_camera_manager()
    return jsonify(cam.get_recent_alerts())


@stream_bp.route("/api/camera/status")
@login_required
def api_camera_status():
    cam = get_camera_manager()
    return jsonify(cam.get_camera_status())


@stream_bp.route("/api/incidents", methods=["GET"])
@login_required
def api_get_incidents():
    incidents = get_all_incidents()
    return jsonify(incidents)


@stream_bp.route("/api/incidents/export.csv", methods=["GET"])
@login_required
def api_export_incidents_csv():
    """Every incident as a CSV download. Each export is logged, since it copies personal data out of the hub."""
    incidents = get_all_incidents_for_export()
    actor = _actor()
    accounts.log_audit(actor, "incidents_exported", f"{len(incidents)} record(s) as CSV")
    filename = f"vigitrack-incidents-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    return Response(
        incidents_to_csv(incidents),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@stream_bp.route("/api/incidents/<int:incident_id>/review", methods=["POST"])
@login_required
def api_review_incident(incident_id):
    """Operators and admins acknowledge, verify or dismiss (as a false alarm) an incident."""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Expected a JSON request."}), 415
    data = request.get_json(silent=True) or {}
    user = _current_user()
    assert user is not None, "login_required has already checked the session"
    action = str(data.get("action") or "")

    incident, error = review_incident(incident_id, action, user["username"], data.get("note"))
    if error:
        status = 404 if error == "Incident not found." else 400
        return jsonify({"status": "error", "message": error}), status
    assert incident is not None

    detail = f"#{incident_id} → {action}"
    if incident["review_note"]:
        detail += f": {incident['review_note']}"
    accounts.log_audit(user["username"], "incident_reviewed", detail)
    return jsonify({"status": "success", "incident": incident})


@stream_bp.route("/api/incidents/<int:incident_id>", methods=["GET"])
@login_required
def api_get_incident(incident_id):
    incident = get_incident(incident_id)
    if incident is None:
        return jsonify({"status": "error", "message": "Incident not found"}), 404
    return jsonify(incident)


@stream_bp.route("/api/incidents/<int:incident_id>/image", methods=["GET"])
@login_required
def api_get_incident_image(incident_id):
    filename = get_incident_image_filename(incident_id)
    if not filename:
        return jsonify({"status": "error", "message": "No snapshot for this incident"}), 404
    # Snapshots show identifiable people, so every view is recorded.
    accounts.log_audit(_actor(), "snapshot_viewed", f"#{incident_id}")
    return send_from_directory(INCIDENT_IMAGE_DIR, filename, mimetype="image/jpeg")


@stream_bp.route("/api/incidents/<int:incident_id>/report.pdf", methods=["GET"])
@login_required
def api_incident_report(incident_id):
    """One-page PDF for a single incident: snapshot, details, timeline and settings used."""
    incident = get_incident(incident_id)
    if incident is None:
        return jsonify({"status": "error", "message": "Incident not found"}), 404

    snapshot = None
    filename = get_incident_image_filename(incident_id)
    if filename:
        try:
            with open(os.path.join(INCIDENT_IMAGE_DIR, os.path.basename(filename)), "rb") as f:
                snapshot = f.read()
        except OSError:
            snapshot = None

    actor = _actor()
    accounts.log_audit(actor, "incident_report_exported", f"#{incident_id}")
    pdf = incident_to_pdf(incident, snapshot, actor)
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="vigitrack-incident-{incident_id}.pdf"'},
    )


@stream_bp.route("/api/incidents/<int:incident_id>", methods=["DELETE"])
@admin_required
def api_delete_incident(incident_id):
    success = delete_incident(incident_id)
    if success:
        accounts.log_audit(_actor(), "incident_deleted", f"#{incident_id}")
    return jsonify({"success": success})


@stream_bp.route("/api/incidents/clear", methods=["POST"])
@admin_required
def api_clear_all_incidents():
    count = clear_all_incidents()
    accounts.log_audit(_actor(), "incidents_cleared", f"{count} records")
    return jsonify({"success": True})


@stream_bp.route("/api/incidents/purge", methods=["POST"])
@admin_required
def api_purge_incidents():
    """Deletes incidents detected between two dates (inclusive), with their snapshots."""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Expected a JSON request."}), 415
    data = request.get_json(silent=True) or {}
    try:
        start = datetime.strptime(str(data.get("start") or ""), "%Y-%m-%d")
        end = datetime.strptime(str(data.get("end") or ""), "%Y-%m-%d")
    except ValueError:
        return jsonify({"status": "error", "message": "Dates must be in the form YYYY-MM-DD."}), 400
    if end < start:
        return jsonify({"status": "error", "message": "The end date is before the start date."}), 400

    end_exclusive = end + timedelta(days=1)
    count = purge_between(start.isoformat(timespec="seconds"), end_exclusive.isoformat(timespec="seconds"))
    actor = _actor()
    accounts.log_audit(actor, "incidents_purged", f"{count} record(s) from {start.date()} to {end.date()}")
    return jsonify({"status": "success", "deleted": count})


@stream_bp.route("/api/zones", methods=["GET"])
@login_required
def api_get_zones():
    return jsonify(get_camera_manager().get_zones())


@stream_bp.route("/api/zones", methods=["POST"])
@admin_required
def api_save_zones():
    """Replaces the ignore and watch zones. Zones are drawn in normalised frame coordinates."""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Expected a JSON request."}), 415
    data = request.get_json(silent=True) or {}
    cam = get_camera_manager()
    old = cam.get_zones()["zones"]
    try:
        saved = cam.set_zones(data.get("zones"))
    except ZoneError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    accounts.log_audit(_actor(), "zones_updated", _zone_changes(old, saved))
    return jsonify({"status": "success", "zones": saved})


@stream_bp.route("/api/settings", methods=["GET"])
@login_required
def api_get_settings():
    cam = get_camera_manager()
    data = cam.get_thresholds()
    data["retention_days"] = int(load_settings().get("retention_days", DEFAULT_RETENTION_DAYS))
    return jsonify(data)


SETTING_LABELS = {
    "distance_threshold": "distance threshold (px)",
    "time_threshold": "time threshold (s)",
    "audio_alert_enabled": "audio alerts",
    "retention_days": "retention (days)",
}


def _audit_settings_changes(actor, before: dict, after: dict) -> None:
    """
    Records what changed with old and new values. Camera sources are masked, so RTSP passwords
    never reach the audit log. A camera switch and a monitored-class change each get their own entry.
    """
    old_source = redact(stored_camera_source(before))
    new_source = redact(stored_camera_source(after))
    if old_source != new_source:
        accounts.log_audit(actor, "camera_switched",
                           f"{old_source} ({before.get('camera_name', '-')}) → {new_source} ({after.get('camera_name', '-')})")

    old_classes = sorted(before.get("monitored_classes", []))
    new_classes = sorted(after.get("monitored_classes", []))
    if old_classes != new_classes:
        accounts.log_audit(actor, "monitored_classes_changed",
                           f"{', '.join(old_classes) or '-'} → {', '.join(new_classes) or '-'}")

    def shown(value):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    changes = [
        f"{label} {shown(before.get(key))} → {shown(after.get(key))}"
        for key, label in SETTING_LABELS.items()
        if before.get(key) != after.get(key)
    ]
    accounts.log_audit(actor, "settings_changed", "; ".join(changes) if changes else "no value changed")


def _zone_summary(zone: dict) -> str:
    kind = zone["type"] if zone["type"] == "ignore" else f"watch {zone.get('time_threshold')} s"
    return f"{zone['name']} ({kind})"


def _zone_changes(old: list, new: list) -> str:
    """Describes which zones were added, removed or edited, matched by zone id."""
    old_by = {z["id"]: z for z in old}
    new_by = {z["id"]: z for z in new}
    parts = [f"added {_zone_summary(z)}" for zid, z in new_by.items() if zid not in old_by]
    parts += [f"removed {_zone_summary(z)}" for zid, z in old_by.items() if zid not in new_by]
    for zid in new_by.keys() & old_by.keys():
        before_z, after_z = old_by[zid], new_by[zid]
        if before_z != after_z:
            parts.append(f"edited {_zone_summary(before_z)} → {_zone_summary(after_z)}")
    return "; ".join(parts) or "no change"


def _parse_monitored_classes(value):
    """Checks a list of class names. 'person' is always included, so it is not required in the list."""
    if not isinstance(value, list) or not all(isinstance(c, str) for c in value):
        raise ValueError("monitored_classes must be a list of class names.")
    known = set(SUPPORTED_CLASSES.values())
    unknown = sorted(set(value) - known)
    if unknown:
        raise ValueError(f"Unknown class: {', '.join(unknown)}. Choose from {', '.join(sorted(known))}.")
    return sorted(set(value) | {"person"})


def _parse_positive_float(value, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive number.")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError(f"{name} must be a positive finite number.")
    return parsed


@stream_bp.route("/api/settings", methods=["POST"])
@admin_required
def api_update_settings():
    if not request.is_json:
        return jsonify({"status": "error", "message": "Expected a JSON request."}), 415

    data = request.get_json(silent=True) or {}
    cam = get_camera_manager()
    actor = _actor()
    before = load_settings()

    try:
        # Validate and parse every value before anything is saved
        has_dist = "distance_threshold" in data
        has_time = "time_threshold" in data
        dist = time_thresh = None
        if has_dist or has_time:
            current = cam.get_thresholds()
            raw_dist = data["distance_threshold"] if has_dist else current.get(
                "distance_threshold", before.get("distance_threshold", 150)
            )
            raw_time = data["time_threshold"] if has_time else current.get(
                "time_threshold", before.get("time_threshold", 10)
            )
            dist = _parse_positive_float(raw_dist, "distance_threshold")
            time_thresh = _parse_positive_float(raw_time, "time_threshold")

        classes = _parse_monitored_classes(data["monitored_classes"]) if "monitored_classes" in data else None

        retention = None
        if "retention_days" in data:
            retention = int(data["retention_days"])
            if not 1 <= retention <= 3650:
                raise ValueError("Retention must be between 1 and 3650 days.")

        # Camera switch first: if it fails, nothing else is saved
        if "camera_source" in data:
            cam.switch_source(data["camera_source"], data.get("camera_name"))

        # switch_source persists its own change, so reload before applying the rest
        s = load_settings()

        if dist is not None and time_thresh is not None:
            cam.update_thresholds(dist, time_thresh)
            s["distance_threshold"] = dist
            s["time_threshold"] = time_thresh

        if "audio_alert_enabled" in data:
            audio_val = bool(data["audio_alert_enabled"])
            cam.notifier.set_audio_enabled(audio_val)
            s["audio_alert_enabled"] = audio_val

        if classes is not None:
            cam.set_monitored_classes(classes)
            s["monitored_classes"] = classes

        if retention is not None:
            s["retention_days"] = retention

        save_settings(s)
        _audit_settings_changes(actor, before, s)

        return jsonify({"status": "success", "settings": cam.get_thresholds()})
    except RuntimeError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except (TypeError, ValueError) as e:
        return jsonify({"status": "error", "message": f"Invalid setting value: {e}"}), 400
