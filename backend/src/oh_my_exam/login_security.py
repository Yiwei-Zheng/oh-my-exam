from __future__ import annotations

import hashlib
import math
import time

from limits import parse
from limits.storage import storage_from_string
from limits.strategies import FixedWindowRateLimiter


ACCOUNT_LIMIT = parse("5 per 15 minutes")
IP_LIMIT = parse("20 per 15 minutes")


class LoginRateLimited(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, retry_after)
        super().__init__("too_many_login_attempts")


class LoginRateLimiter:
    """Apply independent account and client-IP limits using the limits library."""

    def __init__(self, storage_uri: str = "memory://") -> None:
        self._limiter = FixedWindowRateLimiter(storage_from_string(storage_uri))

    def check(self, email: str, client_ip: str) -> None:
        account_key = self._key(email.strip().lower())
        ip_key = self._key(client_ip.strip() or "unknown")
        account_allowed = self._limiter.hit(ACCOUNT_LIMIT, "login-account", account_key)
        ip_allowed = self._limiter.hit(IP_LIMIT, "login-ip", ip_key)
        if account_allowed and ip_allowed:
            return
        account_window = self._limiter.get_window_stats(
            ACCOUNT_LIMIT,
            "login-account",
            account_key,
        )
        ip_window = self._limiter.get_window_stats(IP_LIMIT, "login-ip", ip_key)
        reset_time = max(
            account_window.reset_time if not account_allowed else 0,
            ip_window.reset_time if not ip_allowed else 0,
        )
        raise LoginRateLimited(math.ceil(reset_time - time.time()))

    def reset_account(self, email: str) -> None:
        self._limiter.clear(
            ACCOUNT_LIMIT,
            "login-account",
            self._key(email.strip().lower()),
        )

    @staticmethod
    def _key(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
