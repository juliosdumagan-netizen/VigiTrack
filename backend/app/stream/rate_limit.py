import threading
import time
from collections import deque
from typing import Callable, Deque, Dict, Optional


class FailureLimiter:
    """
    Blocks a key (for example, a client IP address) after too many failures inside a time window.
    The block lifts as the oldest failure leaves the window.
    """

    def __init__(self, max_failures: int = 10, window_seconds: float = 60.0,
                 clock: Callable[[], float] = time.monotonic):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._clock = clock
        self._failures: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> Optional[Deque[float]]:
        failures = self._failures.get(key)
        if failures is None:
            return None
        while failures and now - failures[0] >= self.window_seconds:
            failures.popleft()
        if not failures:
            del self._failures[key]
            return None
        return failures

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            failures = self._recent(key, self._clock())
            return failures is not None and len(failures) >= self.max_failures

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            failures = self._recent(key, now)
            if failures is None:
                failures = self._failures.setdefault(key, deque())
            failures.append(now)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()
