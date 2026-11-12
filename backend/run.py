import os
from datetime import timedelta
from flask import Flask # type: ignore
from app.database.db import init_db
from app.database.users import prepare_first_run
from app.stream.routes import stream_bp
from config.settings_store import load_settings, get_secret_key


def create_app():
    app = Flask(
        __name__,
        static_folder="app/static",
        template_folder="app/stream/templates"
    )
    app.config["SECRET_KEY"] = get_secret_key()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.permanent_session_lifetime = timedelta(hours=8)

    # Initialize database tables; on a fresh install, print the one-time setup code
    init_db()
    prepare_first_run()

    # Register blueprints
    app.register_blueprint(stream_bp)

    return app


if __name__ == "__main__":
    settings = load_settings()
    src = settings.get("camera_source", 0)
    host = os.getenv("VIGITRACK_HOST", "0.0.0.0")
    port = int(os.getenv("VIGITRACK_PORT", "5000"))
    print("=" * 65)
    print("  VigiTrack: AI Surveillance & Unattended Object Detection")
    print(f"  Active Camera Source : {src} ({settings.get('camera_name', 'Default')})")
    print(f"  Dashboard URL        : http://127.0.0.1:{port}")
    print("  Press Ctrl + C in terminal to stop.")
    print("=" * 65)

    app = create_app()
    # Note: debug=False prevents duplicate camera initialization by the Flask reloader
    app.run(host=host, port=port, threaded=True, debug=False)
