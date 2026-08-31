from __future__ import annotations

from contextlib import contextmanager
from email.utils import parsedate_to_datetime
import math
from threading import Condition
import time
from typing import Iterator
import urllib.error


class AdaptiveRateLimiter:
    """A small AIMD request gate shared by workers targeting one server."""

    def __init__(
        self,
        max_concurrency: int,
        *,
        initial_interval_seconds: float = 0.2,
        minimum_interval_seconds: float = 0.02,
    ) -> None:
        self.max_concurrency = max(1, int(max_concurrency))
        self.window = 1
        self.interval_seconds = max(
            minimum_interval_seconds,
            float(initial_interval_seconds),
        )
        self.minimum_interval_seconds = max(0.0, minimum_interval_seconds)
        self._active = 0
        self._successes = 0
        self._next_start = 0.0
        self._cooldown_until = 0.0
        self._condition = Condition()

    @contextmanager
    def slot(self) -> Iterator[None]:
        self._acquire()
        try:
            yield
        except urllib.error.HTTPError as exc:
            if exc.code in {429, 503}:
                self.record_rate_limit(_retry_after_seconds(exc))
            raise
        else:
            self.record_success()
        finally:
            with self._condition:
                self._active -= 1
                self._condition.notify_all()

    def record_success(self) -> None:
        with self._condition:
            self._successes += 1
            if self._successes < max(4, self.window * 4):
                return
            self._successes = 0
            self.window = min(self.max_concurrency, self.window + 1)
            self.interval_seconds = max(
                self.minimum_interval_seconds,
                self.interval_seconds * 0.85,
            )
            self._condition.notify_all()

    def record_rate_limit(self, retry_after_seconds: float | None = None) -> None:
        with self._condition:
            self.window = max(1, math.ceil(self.window / 2))
            self.interval_seconds = min(
                30.0,
                max(0.25, self.interval_seconds * 2),
            )
            cooldown = (
                retry_after_seconds
                if retry_after_seconds is not None
                else max(1.0, self.interval_seconds * 4)
            )
            self._cooldown_until = max(
                self._cooldown_until,
                time.monotonic() + cooldown,
            )
            self._successes = 0
            self._condition.notify_all()

    def _acquire(self) -> None:
        with self._condition:
            while True:
                now = time.monotonic()
                wait_seconds = max(
                    0.0,
                    self._cooldown_until - now,
                    self._next_start - now,
                )
                if self._active < self.window and wait_seconds <= 0:
                    self._active += 1
                    self._next_start = now + self.interval_seconds
                    return
                self._condition.wait(timeout=wait_seconds or 0.05)


def _retry_after_seconds(exc: urllib.error.HTTPError) -> float | None:
    value = exc.headers.get("Retry-After") if exc.headers else None
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            return max(0.0, parsed.timestamp() - time.time())
        except (TypeError, ValueError, OverflowError):
            return None
