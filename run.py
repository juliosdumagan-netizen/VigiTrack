import sys
import types
from enum import IntEnum

# Compatibility guard for PyTorch 2.5+ legacy datapipes imports if needed
try:
    import torch.utils.data.datapipes  # type: ignore
except (ImportError, ModuleNotFoundError):
    try:
        import torch.utils.data as tud  # type: ignore

        class SHARDING_PRIORITIES(IntEnum):
            DEFAULT = 1

        sharding_mod = types.ModuleType("torch.utils.data.datapipes.iter.sharding")
        sharding_mod.SHARDING_PRIORITIES = SHARDING_PRIORITIES  # type: ignore

        iter_mod = types.ModuleType("torch.utils.data.datapipes.iter")
        iter_mod.sharding = sharding_mod  # type: ignore

        dp_mod = types.ModuleType("torch.utils.data.datapipes")
        dp_mod.iter = iter_mod  # type: ignore

        tud.datapipes = dp_mod  # type: ignore
        sys.modules["torch.utils.data.datapipes"] = dp_mod
        sys.modules["torch.utils.data.datapipes.iter"] = iter_mod
        sys.modules["torch.utils.data.datapipes.iter.sharding"] = sharding_mod
    except Exception:
        pass

import os
from flask import Flask
from app.database.db import init_db
from app.stream.routes import stream_bp
from config.settings_store import load_settings


def create_app():
    app = Flask(
        __name__,
        static_folder="app/static",
        template_folder="app/stream/templates"
    )
    app.config["SECRET_KEY"] = "vigitrack-secure-key"

    # Initialize database tables
    init_db()

    # Register blueprints
    app.register_blueprint(stream_bp)

    return app


if __name__ == "__main__":
    settings = load_settings()
    src = settings.get("camera_source", 0)
    print("=" * 65)
    print("  VigiTrack: AI Surveillance & Unattended Object Detection")
    print(f"  Active Camera Source : {src} ({settings.get('camera_name', 'Default')})")
    print("  Dashboard URL        : http://127.0.0.1:5000")
    print("  Press Ctrl + C in terminal to stop.")
    print("=" * 65)

    app = create_app()
    # Note: debug=False prevents duplicate camera initialization by the Flask reloader
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)
