from __future__ import annotations

import pytest

from oh_my_exam.login_security import LoginRateLimited, LoginRateLimiter


def test_account_limit_and_successful_login_reset() -> None:
    limiter = LoginRateLimiter()

    for _ in range(4):
        limiter.check("admin@example.com", "127.0.0.1")
    limiter.reset_account("ADMIN@example.com")
    for _ in range(5):
        limiter.check("admin@example.com", "127.0.0.2")

    with pytest.raises(LoginRateLimited) as error:
        limiter.check("admin@example.com", "127.0.0.2")
    assert 1 <= error.value.retry_after <= 15 * 60


def test_ip_limit_applies_across_account_names() -> None:
    limiter = LoginRateLimiter()

    for index in range(20):
        limiter.check(f"user-{index}@example.com", "203.0.113.4")

    with pytest.raises(LoginRateLimited):
        limiter.check("another@example.com", "203.0.113.4")
