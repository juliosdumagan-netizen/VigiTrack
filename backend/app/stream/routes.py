import os
import threading
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, Response, jsonify, request, session, redirect, send_from_directory
from werkzeug.security import check_password_hash
from app.database.retention import DEFAULT_RETENTION_DAYS, purge_between
from app.detection.classes import SUPPORTED_CLASSES
from app.stream.camera_manager import CameraManager
from app.stream.rate_limit import FailureLimiter
from app.database.models import (
    INCIDENT_IMAGE_DIR,
    clear_all_incidents,
    delete_incident,
    get_all_incidents,
    get_incident,
    get_incident_image_filename,
    review_incident,
)
from app.database import users as accounts
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


def generate_frames():
    """Generator streaming multipart MJPEG frames to web clients."""
    cam = get_camera_manager()
    while True:
        frame_bytes = cam.get_frame()
        if frame_bytes is not None:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
        time.sleep(0.03)  # ~30 FPS throttle for streaming


IDLE_TIMEOUT_SECONDS = int(os.getenv("VIGITRACK_IDLE_MINUTES", "30")) * 60

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
    user = accounts.get_user(user_id)
    if user is None or not user["is_active"]:
        session.clear()
        return None

    now = time.time()
    last_seen = session.get("last_seen")
    if last_seen is not None and now - last_seen > IDLE_TIMEOUT_SECONDS:
        accounts.log_audit(user["username"], "session_expired", "idle timeout")
        session.clear()
        return None
    if last_seen is None or request.endpoint not in BACKGROUND_ENDPOINTS:
        session["last_seen"] = now
    return user


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
    password = (data.get("password") or "").strip()

    user, reason = accounts.authenticate(username, password)
    if not user:
        login_limiter.record_failure(_client_ip())
    if user:
        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        session["last_seen"] = time.time()
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
        "message": messages.get(reason, "Invalid username or password."),
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
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["last_seen"] = time.time()
    return jsonify({"status": "success", "user": user}), 201


@stream_bp.route("/api/logout", methods=["POST"])
def api_logout():
    user = _current_user()
    if user:
        accounts.log_audit(user["username"], "logout")
    session.clear()
    return jsonify({"status": "success"})


@stream_bp.route("/logout")
def logout():
    """Ends the session and redirects back to the hub's start page."""
    user = _current_user()
    if user:
        accounts.log_audit(user["username"], "logout")
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
    actor = _current_user()["username"]
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    role = str(data.get("role") or "operator")

    user, error = accounts.create_user(username, password, role, must_change=True)
    if error:
        return jsonify({"status": "error", "message": error}), 400
    accounts.log_audit(actor, "user_created", f"{user['username']} ({user['role']})")
    return jsonify({"status": "success", "user": user}), 201


@stream_bp.route("/api/users/<int:user_id>", methods=["PATCH"])
@admin_required
def api_update_user(user_id):
    if not request.is_json:
        return jsonify({"status": "error", "message": "Expected a JSON request."}), 415
    actor_user = _current_user()
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


# =========================================================================
# Protected Surveillance & Management Routes
# =========================================================================

@stream_bp.route("/video_feed")
@login_required
def video_feed():
    """Protected live MJPEG video stream."""
    return Response(
        generate_frames(),
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


@stream_bp.route("/api/incidents/<int:incident_id>/review", methods=["POST"])
@login_required
def api_review_incident(incident_id):
    """Operators and admins acknowledge, verify or dismiss (as a false alarm) an incident."""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Expected a JSON request."}), 415
    data = request.get_json(silent=True) or {}
    user = _current_user()
    action = str(data.get("action") or "")

    incident, error = review_incident(incident_id, action, user["username"], data.get("note"))
    if error:
        status = 404 if error == "Incident not found." else 400
        return jsonify({"status": "error", "message": error}), status

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
    return send_from_directory(INCIDENT_IMAGE_DIR, filename, mimetype="image/jpeg")


@stream_bp.route("/api/incidents/<int:incident_id>", methods=["DELETE"])
@admin_required
def api_delete_incident(incident_id):
    success = delete_incident(incident_id)
    if success:
        accounts.log_audit(_current_user()["username"], "incident_deleted", f"#{incident_id}")
    return jsonify({"success": success})


@stream_bp.route("/api/incidents/clear", methods=["POST"])
@admin_required
def api_clear_all_incidents():
    count = clear_all_incidents()
    accounts.log_audit(_current_user()["username"], "incidents_cleared", f"{count} records")
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
    actor = _current_user()["username"]
    accounts.log_audit(actor, "incidents_purged", f"{count} record(s) from {start.date()} to {end.date()}")
    return jsonify({"status": "success", "deleted": count})


@stream_bp.route("/api/settings", methods=["GET"])
@login_required
def api_get_settings():
    cam = get_camera_manager()
    data = cam.get_thresholds()
    data["retention_days"] = int(load_settings().get("retention_days", DEFAULT_RETENTION_DAYS))
    return jsonify(data)


def _parse_monitored_classes(value):
    """Checks a list of class names. 'person' is always included, so it is not required in the list."""
    if not isinstance(value, list) or not all(isinstance(c, str) for c in value):
        raise ValueError("monitored_classes must be a list of class names.")
    known = set(SUPPORTED_CLASSES.values())
    unknown = sorted(set(value) - known)
    if unknown:
        raise ValueError(f"Unknown class: {', '.join(unknown)}. Choose from {', '.join(sorted(known))}.")
    return sorted(set(value) | {"person"})


@stream_bp.route("/api/settings", methods=["POST"])
@admin_required
def api_update_settings():
    if not request.is_json:
        return jsonify({"status": "error", "message": "Expected a JSON request."}), 415

    data = request.get_json(silent=True) or {}
    cam = get_camera_manager()
    actor = _current_user()["username"]

    try:
        # Validate and parse every value before anything is saved
        dist = time_thresh = None
        if "distance_threshold" in data and "time_threshold" in data:
            dist = float(data["distance_threshold"])
            time_thresh = float(data["time_threshold"])

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

        if dist is not None:
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
        accounts.log_audit(actor, "settings_changed", ", ".join(sorted(data.keys())))

        return jsonify({"status": "success", "settings": cam.get_thresholds()})
    except RuntimeError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except (TypeError, ValueError) as e:
        return jsonify({"status": "error", "message": f"Invalid setting value: {e}"}), 400
