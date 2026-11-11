import time
from functools import wraps
from flask import Blueprint, render_template, Response, jsonify, request, session, redirect, url_for
from app.stream.camera_manager import CameraManager
from app.database.models import get_all_incidents, delete_incident, clear_all_incidents
from config.settings_store import load_settings, save_settings

stream_bp = Blueprint(
    "stream_bp",
    __name__,
    template_folder="templates"
)

# Global camera manager instance
camera_manager = None


def get_camera_manager():
    global camera_manager
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


def admin_required(f):
    """Decorator guarding surveillance monitoring routes for authorized administrators."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"status": "unauthorized", "message": "Authentication required. Please login as admin."}), 401
            return redirect(url_for("stream_bp.landing", login="required"))
        return f(*args, **kwargs)
    return decorated_function


# =========================================================================
# Public Landing & Authentication Routes
# =========================================================================

@stream_bp.route("/")
def landing():
    """Public landing page showcasing VigiTrack with sleek hero & Admin portal trigger."""
    is_logged_in = bool(session.get("admin_logged_in"))
    prompt_login = request.args.get("login") == "required"
    return render_template("landing.html", is_logged_in=is_logged_in, prompt_login=prompt_login)


@stream_bp.route("/api/login", methods=["POST"])
def api_login():
    """Validates admin credentials and establishes an authenticated session."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    settings = load_settings()
    valid_user = settings.get("admin_username", "admin")
    valid_pass = settings.get("admin_password", "admin123")

    if username == valid_user and password == valid_pass:
        session["admin_logged_in"] = True
        return jsonify({
            "status": "success",
            "message": "Authentication successful",
            "redirect": "/dashboard"
        })

    return jsonify({
        "status": "error",
        "message": "Invalid Administrator credentials. Please verify username and password."
    }), 401


@stream_bp.route("/logout")
def logout():
    """Terminates admin session and redirects back to landing page."""
    session.pop("admin_logged_in", None)
    return redirect(url_for("stream_bp.landing"))


# =========================================================================
# Protected Surveillance & Management Routes (Admin Only)
# =========================================================================

@stream_bp.route("/dashboard")
@admin_required
def dashboard():
    """Live surveillance monitoring dashboard."""
    cam = get_camera_manager()
    return render_template("dashboard.html", camera_name=cam.camera_name)


@stream_bp.route("/incidents")
@admin_required
def incidents_page():
    return render_template("incidents.html")


@stream_bp.route("/settings")
@admin_required
def settings_page():
    return render_template("settings.html")


@stream_bp.route("/video_feed")
@admin_required
def video_feed():
    """Protected live MJPEG video stream."""
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@stream_bp.route("/api/alerts")
@admin_required
def api_alerts():
    cam = get_camera_manager()
    return jsonify(cam.get_recent_alerts())


@stream_bp.route("/api/incidents", methods=["GET"])
@admin_required
def api_get_incidents():
    incidents = get_all_incidents()
    return jsonify(incidents)


@stream_bp.route("/api/incidents/<int:incident_id>", methods=["DELETE"])
@admin_required
def api_delete_incident(incident_id):
    success = delete_incident(incident_id)
    return jsonify({"success": success})


@stream_bp.route("/api/incidents/clear", methods=["POST"])
@admin_required
def api_clear_all_incidents():
    success = clear_all_incidents()
    return jsonify({"success": success})


@stream_bp.route("/api/settings", methods=["GET"])
@admin_required
def api_get_settings():
    cam = get_camera_manager()
    thresholds = cam.get_thresholds()
    s = load_settings()
    thresholds["admin_username"] = s.get("admin_username", "admin")
    return jsonify(thresholds)


@stream_bp.route("/api/settings", methods=["POST"])
@admin_required
def api_update_settings():
    data = request.get_json(silent=True) or {}
    cam = get_camera_manager()

    try:
        s = load_settings()

        # Distance & Time thresholds
        if "distance_threshold" in data and "time_threshold" in data:
            dist = float(data["distance_threshold"])
            time_thresh = float(data["time_threshold"])
            cam.update_thresholds(dist, time_thresh)
            s["distance_threshold"] = dist
            s["time_threshold"] = time_thresh

        # Audio toggle
        if "audio_alert_enabled" in data:
            audio_val = bool(data["audio_alert_enabled"])
            cam.notifier.set_audio_enabled(audio_val)
            s["audio_alert_enabled"] = audio_val

        # Admin credentials
        if "admin_username" in data and data["admin_username"]:
            s["admin_username"] = str(data["admin_username"]).strip()
        if "admin_password" in data and data["admin_password"]:
            s["admin_password"] = str(data["admin_password"]).strip()

        save_settings(s)

        # Camera source switch if provided
        if "camera_source" in data:
            cam_src = data["camera_source"]
            cam_name = data.get("camera_name")
            cam.switch_source(cam_src, cam_name)

        resp = cam.get_thresholds()
        resp["admin_username"] = s.get("admin_username", "admin")
        return jsonify({"status": "success", "settings": resp})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
