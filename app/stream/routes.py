import time
from flask import Blueprint, render_template, Response, jsonify, request
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


@stream_bp.route("/")
def dashboard():
    cam = get_camera_manager()
    return render_template("dashboard.html", camera_name=cam.camera_name)


@stream_bp.route("/incidents")
def incidents_page():
    return render_template("incidents.html")


@stream_bp.route("/settings")
def settings_page():
    return render_template("settings.html")


@stream_bp.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@stream_bp.route("/api/alerts")
def api_alerts():
    cam = get_camera_manager()
    return jsonify(cam.get_recent_alerts())


@stream_bp.route("/api/incidents", methods=["GET"])
def api_get_incidents():
    incidents = get_all_incidents()
    return jsonify(incidents)


@stream_bp.route("/api/incidents/<int:incident_id>", methods=["DELETE"])
def api_delete_incident(incident_id):
    success = delete_incident(incident_id)
    return jsonify({"success": success})


@stream_bp.route("/api/incidents/clear", methods=["POST"])
def api_clear_all_incidents():
    success = clear_all_incidents()
    return jsonify({"success": success})


@stream_bp.route("/api/settings", methods=["GET"])
def api_get_settings():
    cam = get_camera_manager()
    thresholds = cam.get_thresholds()
    return jsonify(thresholds)


@stream_bp.route("/api/settings", methods=["POST"])
def api_update_settings():
    data = request.get_json(silent=True) or {}
    cam = get_camera_manager()

    try:
        # Distance & Time thresholds
        if "distance_threshold" in data and "time_threshold" in data:
            dist = float(data["distance_threshold"])
            time_thresh = float(data["time_threshold"])
            cam.update_thresholds(dist, time_thresh)

        # Audio toggle
        if "audio_alert_enabled" in data:
            audio_val = bool(data["audio_alert_enabled"])
            cam.notifier.set_audio_enabled(audio_val)
            s = load_settings()
            s["audio_alert_enabled"] = audio_val
            save_settings(s)

        # Camera source switch if provided
        if "camera_source" in data:
            cam_src = data["camera_source"]
            cam_name = data.get("camera_name")
            cam.switch_source(cam_src, cam_name)

        return jsonify({"status": "success", "settings": cam.get_thresholds()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
