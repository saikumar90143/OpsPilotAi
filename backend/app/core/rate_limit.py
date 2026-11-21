"""In-memory sliding-window rate limiter for authentication endpoints.

Abstracted behind ``RateLimiter`` so Phase 4 can swap in a Redis-backed
implementation without changing callers.
"""

import threading
import time
from collections import defaultdict, deque

from app.core.errors import RateLimitedError


class RateLimiter:
    """Thread-safe per-key sliding-window rate limiter."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, *, max_requests: int, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= max_requests:
                raise RateLimitedError("Too many authentication attempts. Please try again later.")
            bucket.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


auth_rate_limiter = RateLimiter()
