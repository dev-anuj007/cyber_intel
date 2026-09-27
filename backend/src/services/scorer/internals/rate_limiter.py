import threading
import time


class GlobalRateLimiter:
    def __init__(self, min_interval: float = 0.05) -> None:
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._last_call_time = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_call_time = time.time()


global_rate_limiter = GlobalRateLimiter(min_interval=0.05)
