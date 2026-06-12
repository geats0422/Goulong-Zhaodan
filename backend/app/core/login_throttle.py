from __future__ import annotations

import time
from collections import defaultdict


class LoginThrottle:
    def __init__(self) -> None:
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, key: str) -> None:
        now = time.monotonic()
        self._attempts[key] = [t for t in self._attempts[key] if now - t < 300]

    def record_failure(self, key: str) -> None:
        self._cleanup(key)
        self._attempts[key].append(time.monotonic())

    def get_wait_seconds(self, key: str) -> int:
        self._cleanup(key)
        count = len(self._attempts[key])
        if count < 5:
            return 0
        elif count < 10:
            return 30
        elif count < 15:
            return 60
        else:
            return 300

    def check(self, key: str) -> int:
        return self.get_wait_seconds(key)

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)


login_throttle = LoginThrottle()
