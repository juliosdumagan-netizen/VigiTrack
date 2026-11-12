import os
import json
import secrets

from werkzeug.security import generate_password_hash # type: ignore

SETTINGS_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")
)

DEFAULTS = {
    "distance_threshold": 150,
    "time_threshold": 10,
    "monitored_classes": ["person", "backpack", "handbag", "suitcase"],
    "audio_alert_enabled": True,
    "camera_source": 0,
    "camera_name": "BUILT-IN WEBCAM"
}


def load_settings() -> dict:
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    if not os.path.exists(SETTINGS_PATH):
        save_settings(DEFAULTS)
        return DEFAULTS.copy()
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        save_settings(DEFAULTS)
        return DEFAULTS.copy()

    merged = DEFAULTS.copy()
    merged.update(data)

    if "admin_password" in data:
        merged["admin_password_hash"] = generate_password_hash(str(data["admin_password"]))
        merged.pop("admin_password", None)
        save_settings(merged)

    return merged


def save_settings(settings: dict) -> bool:
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        return True
    except OSError as e:
        print(f"[SettingsStore Error] Failed to write {SETTINGS_PATH}: {e}")
        return False


def get_secret_key() -> str:
    """Returns the Flask session key, generating and persisting one on first use."""
    env_key = os.getenv("VIGITRACK_SECRET_KEY")
    if env_key:
        return env_key

    settings = load_settings()
    key = settings.get("secret_key")
    if not key:
        key = secrets.token_hex(32)
        settings["secret_key"] = key
        save_settings(settings)
    return key
