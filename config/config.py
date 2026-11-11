import os
from config.settings_store import load_settings


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "vigitrack-dev-key")
    DEBUG = os.getenv("FLASK_DEBUG", "False") == "True"

    SUPPORTED_CLASSES = {
        0: "person",
        24: "backpack",
        26: "handbag",
        28: "suitcase",
    }

    @staticmethod
    def get_active_settings():
        return load_settings()
