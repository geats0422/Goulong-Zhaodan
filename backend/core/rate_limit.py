from __future__ import annotations

import time
from collections import defaultdict


class IPRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, now: float) -> None:
        cutoff = now - self._window
        keys = list(self._requests.keys())
        for k in keys:
            self._requests[k] = [t for t in self._requests[k] if t > cutoff]
            if not self._requests[k]:
                del self._requests[k]

    def is_limited(self, ip: str) -> bool:
        now = time.time()
        self._cleanup(now)
        return len(self._requests[ip]) >= self._max

    def record(self, ip: str) -> None:
        self._requests[ip].append(time.time())

    def reset(self) -> None:
        self._requests.clear()


register_limiter = IPRateLimiter(max_requests=5, window_seconds=3600)
