from typing import Optional, Tuple

ONLINE_WITHIN_SECONDS = 3.0
OFFLINE_AFTER_SECONDS = 10.0


def classify(last_frame_at: Optional[float], now: float) -> Tuple[str, Optional[float]]:
    """
    Turns the time of the last good frame into a camera status.
    Returns (status, age_in_seconds). Status is 'online', 'reconnecting' or 'offline'.
    """
    if last_frame_at is None:
        return "offline", None
    age = max(0.0, now - last_frame_at)
    if age < ONLINE_WITHIN_SECONDS:
        return "online", age
    if age < OFFLINE_AFTER_SECONDS:
        return "reconnecting", age
    return "offline", age
