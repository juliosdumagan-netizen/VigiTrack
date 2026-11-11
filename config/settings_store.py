import os
import json

SETTINGS_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")
)

DEFAULTS = {
    "distance_threshold": 150,
    "time_threshold": 10,
    "confidence_person": 0.60,
    "confidence_bag": 0.20,
    "monitored_classes": ["person", "backpack", "handbag", "suitcase"],
    "audio_alert_enabled": True,
    "camera_source": 0,
    "camera_name": "BUILT-IN WEBCAM",
    "admin_username": "admin",
    "admin_password": "admin123"
}


def load_settings() -> dict:
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    if not os.path.exists(SETTINGS_PATH):
        save_settings(DEFAULTS)
        return DEFAULTS.copy()
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = DEFAULTS.copy()
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        save_settings(DEFAULTS)
        return DEFAULTS.copy()


def save_settings(settings: dict) -> bool:
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        return True
    except OSError as e:
        print(f"[SettingsStore Error] Failed to write {SETTINGS_PATH}: {e}")
        return False
