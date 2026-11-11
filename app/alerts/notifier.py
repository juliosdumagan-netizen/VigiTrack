import sys
import threading
import time
import cv2


class Notifier:
    """
    Manages audio and visual notifications for unattended object alerts.
    - Rate-limited/debounced beep on Windows using winsound.
    - Threaded audio playback so video capture/inference is never blocked.
    - Top banner overlay on the video feed.
    """

    def __init__(self, audio_enabled: bool = True, debounce_seconds: float = 3.0):
        self.audio_enabled = audio_enabled
        self.debounce_seconds = debounce_seconds
        self.last_sound_time = 0.0
        self._lock = threading.Lock()

    def set_audio_enabled(self, enabled: bool):
        with self._lock:
            self.audio_enabled = bool(enabled)

    def play_alert_sound(self, object_id=None):
        """Plays a warning sound in a background thread if audio is enabled and debounced."""
        if not self.audio_enabled:
            return

        now = time.time()
        with self._lock:
            if now - self.last_sound_time < self.debounce_seconds:
                return
            self.last_sound_time = now

        def _beep():
            try:
                if sys.platform == "win32":
                    import winsound
                    # 1200 Hz tone for 350 ms
                    winsound.Beep(1200, 350)
                else:
                    print("\a", end="", flush=True)
            except Exception as e:
                print(f"[Notifier] Audio error: {e}")

        threading.Thread(target=_beep, daemon=True).start()

    def draw_alert_banner(self, frame, message="WARNING: UNATTENDED OBJECT DETECTED"):
        """Draws a red alert banner across the top of the video frame."""
        h, w = frame.shape[:2]
        banner_h = max(40, int(h * 0.08))

        # Semi-transparent red banner background
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, banner_h), (0, 0, 180), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        # White warning text with subtle shadow
        text = message
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = max(0.6, banner_h / 65.0)
        thickness = 2
        (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
        tx = max(10, (w - tw) // 2)
        ty = (banner_h + th) // 2 - 2

        cv2.putText(frame, text, (tx + 1, ty + 1), font, font_scale, (0, 0, 0), thickness + 1, cv2.LINE_AA)
        cv2.putText(frame, text, (tx, ty), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
        return frame
