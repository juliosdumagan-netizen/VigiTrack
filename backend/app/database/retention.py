import threading
import time
from datetime import datetime, timedelta

from app.database.models import delete_incidents_where
from app.database.users import log_audit
from config.settings_store import load_settings

DEFAULT_RETENTION_DAYS = 30
CHECK_INTERVAL_SECONDS = 3600


def purge_older_than(days: int) -> int:
    """Deletes incidents and snapshots older than the given number of days. Logs the run if anything was removed."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    count = delete_incidents_where("detected_at < ?", (cutoff,))
    if count:
        log_audit("system", "retention_purged", f"{count} incident(s) older than {days} days")
    return count


def purge_between(start_iso: str, end_iso: str) -> int:
    """Deletes incidents detected from start (inclusive) to end (exclusive). Both are ISO timestamps."""
    return delete_incidents_where("detected_at >= ? AND detected_at < ?", (start_iso, end_iso))


def _loop():
    while True:
        try:
            days = int(load_settings().get("retention_days", DEFAULT_RETENTION_DAYS))
            purge_older_than(days)
        except Exception as e:
            print(f"[Retention Error] {e}")
        time.sleep(CHECK_INTERVAL_SECONDS)


def start_retention_worker():
    """Runs the retention check now and then every hour, on a background thread."""
    threading.Thread(target=_loop, daemon=True, name="VigiTrack-Retention").start()
