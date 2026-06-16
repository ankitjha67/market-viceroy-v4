"""Tests for alphakit.data.rate_limit.

Tests drive the token bucket with a fake clock and a fake sleeper so
they never rely on wall-clock timing.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator

import pytest
from alphakit.data.rate_limit import (
    _DEFAULT_FALLBACK,
    _DEFAULTS,
    _env_limit,
    _TokenBucket,
    acquire,
    reset,
)


@pytest.fixture(autouse=True)
def reset_buckets() -> Iterator[None]:
    reset()
    yield
    reset()


def _fake_clock() -> tuple[Callable[[], float], Callable[[float], None], list[float]]:
    """Return ``(monotonic, sleeper, sleep_log)`` sharing a mutable clock."""
    clock = [0.0]
    sleeps: list[float] = []

    def monotonic() -> float:
        return clock[0]

    def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += seconds

    return monotonic, sleeper, sleeps


def test_acquire_is_immediate_when_bucket_full() -> None:
    monotonic, sleeper, sleeps = _fake_clock()
    bucket = _TokenBucket(60, monotonic=monotonic, sleeper=sleeper)
    for _ in range(60):
        bucket.acquire()
    assert sleeps == [], "Full bucket should not sleep"


def test_acquire_blocks_when_empty_and_waits_for_refill() -> None:
    monotonic, sleeper, sleeps = _fake_clock()
    bucket = _TokenBucket(60, monotonic=monotonic, sleeper=sleeper)
    # Drain the bucket.
    for _ in range(60):
        bucket.acquire()
    # Next acquire must wait roughly 1 second (60/min = 1/sec).
    bucket.acquire()
    assert len(sleeps) >= 1
    assert sum(sleeps) == pytest.approx(1.0, rel=0.05)


def test_rejects_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="positive"):
        _TokenBucket(0)
    with pytest.raises(ValueError, match="positive"):
        _TokenBucket(-5)


def test_env_var_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHAKIT_RATELIMIT_FRED_PER_MINUTE", "30")
    assert _env_limit("fred") == 30


def test_env_var_for_hyphenated_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHAKIT_RATELIMIT_CFTC_COT_PER_MINUTE", "5")
    assert _env_limit("cftc-cot") == 5


def test_invalid_env_var_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHAKIT_RATELIMIT_FRED_PER_MINUTE", "not-a-number")
    with pytest.raises(ValueError, match="must be int"):
        _env_limit("fred")


def test_negative_env_var_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHAKIT_RATELIMIT_FRED_PER_MINUTE", "-1")
    with pytest.raises(ValueError, match="must be positive"):
        _env_limit("fred")


def test_default_fallback_for_unknown_feed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALPHAKIT_RATELIMIT_SOME_NEW_FEED_PER_MINUTE", raising=False)
    assert _env_limit("some-new-feed") == _DEFAULT_FALLBACK


def test_known_feed_defaults_match_plan() -> None:
    assert _DEFAULTS["fred"] == 120
    assert _DEFAULTS["yfinance"] == 60
    assert _DEFAULTS["eia"] == 80
    assert _DEFAULTS["cftc"] == 10


def test_per_feed_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Draining one feed must not affect another feed's quota."""
    # Use a generous limit so acquire never has to wait.
    monkeypatch.setenv("ALPHAKIT_RATELIMIT_FEED_A_PER_MINUTE", "1000")
    monkeypatch.setenv("ALPHAKIT_RATELIMIT_FEED_B_PER_MINUTE", "1000")
    for _ in range(10):
        acquire("feed-a")
    # feed-b still full; this must not block.
    acquire("feed-b")


def test_env_lookup_uppercases_and_substitutes_dashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHAKIT_RATELIMIT_YFINANCE_FUTURES_PER_MINUTE", "45")
    assert _env_limit("yfinance-futures") == 45


def test_env_var_trumps_builtin_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHAKIT_RATELIMIT_EIA_PER_MINUTE", "999")
    assert _env_limit("eia") == 999


def test_env_var_is_read_lazily() -> None:
    """Env var set *after* import still takes effect when bucket is built."""
    os.environ["ALPHAKIT_RATELIMIT_LAZY_FEED_PER_MINUTE"] = "42"
    try:
        assert _env_limit("lazy-feed") == 42
    finally:
        del os.environ["ALPHAKIT_RATELIMIT_LAZY_FEED_PER_MINUTE"]
