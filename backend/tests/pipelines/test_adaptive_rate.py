import urllib.error

import pytest

from oh_my_exam.pipelines.adaptive_rate import AdaptiveRateLimiter


def test_adaptive_limiter_increases_then_backs_off() -> None:
    limiter = AdaptiveRateLimiter(8, initial_interval_seconds=0.2)

    for _ in range(4):
        limiter.record_success()

    assert limiter.window == 2
    assert limiter.interval_seconds < 0.2

    with pytest.raises(urllib.error.HTTPError):
        with limiter.slot():
            raise urllib.error.HTTPError(
                "https://example.test/file.pdf",
                429,
                "rate limited",
                {"Retry-After": "0"},
                None,
            )

    assert limiter.window == 1
    assert limiter.interval_seconds >= 0.25
