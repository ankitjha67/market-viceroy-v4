"""Per-feed token-bucket rate limiter.

Free feeds have quotas: FRED allows 120 req/min, EIA 80 req/min, and
yfinance has undocumented throttling that varies by endpoint. When the
benchmark runner parallelises strategies that all pull from the same
feed, the quota burns in seconds unless calls are serialised.

This module keeps per-feed state in a process-global dict and exposes
one function — :func:`acquire` — that blocks until a token is available.
It is intentionally single-process: Phase 2 backtests run in one Python
process. Multi-process coordination (live trading, distributed runners)
is Phase 5 work and will require a different mechanism (shared memory,
redis, etc.); ADR-007 tracks the deferral.

Configuration
-------------
Limits come from the environment:

    ALPHAKIT_RATELIMIT_FRED_PER_MINUTE=60
    ALPHAKIT_RATELIMIT_YFINANCE_PER_MINUTE=30

The env-var name is derived from the feed name, uppercased, with ``-``
replaced by ``_``. Values must be positive integers; invalid values
raise ``ValueError`` when the limiter is first used for that feed.
Built-in defaults match the plan: FRED 120, YFINANCE 60, EIA 80,
CFTC 10.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable

_DEFAULTS: dict[str, int] = {
    "fred": 120,
    "yfinance": 60,
    "yfinance-futures": 60,
    "eia": 80,
    "cftc": 10,
    "cftc-cot": 10,
}

_DEFAULT_FALLBACK = 60

_BUCKETS: dict[str, _TokenBucket] = {}
_BUCKETS_LOCK = threading.Lock()


class _TokenBucket:
    """Thread-safe token bucket with wall-clock replenishment.

    Capacity equals the per-minute limit; tokens replenish at that same
    rate continuously. ``acquire`` takes one token, blocking (via the
    supplied sleeper) until a token is available. The ``monotonic`` and
    ``sleeper`` hooks exist so tests can drive the bucket with a fake
    clock.
    """

    def __init__(
        self,
        per_minute: int,
        *,
        monotonic: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        if per_minute <= 0:
            raise ValueError(f"Rate limit must be positive, got {per_minute}")
        self.capacity: float = float(per_minute)
        self.rate_per_second: float = per_minute / 60.0
        self._tokens: float = float(per_minute)
        self._monotonic: Callable[[], float] = (
            monotonic if monotonic is not None else time.monotonic
        )
        self._sleep: Callable[[float], None] = sleeper if sleeper is not None else time.sleep
        self._last: float = self._monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until one token is available, then consume it."""
        while True:
            with self._lock:
                now = self._monotonic()
                elapsed = now - self._last
                if elapsed > 0:
                    self._tokens = min(
                        self.capacity,
                        self._tokens + elapsed * self.rate_per_second,
                    )
                    self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                deficit = 1.0 - self._tokens
                wait = deficit / self.rate_per_second
            self._sleep(wait)


def _env_limit(feed_name: str) -> int:
    """Resolve the per-minute limit for ``feed_name`` from env + defaults."""
    key = f"ALPHAKIT_RATELIMIT_{feed_name.upper().replace('-', '_')}_PER_MINUTE"
    raw = os.environ.get(key)
    if raw is not None:
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"Invalid rate-limit env var {key}={raw!r}; must be int") from exc
        if value <= 0:
            raise ValueError(f"Rate limit {key}={raw!r} must be positive")
        return value
    return _DEFAULTS.get(feed_name, _DEFAULT_FALLBACK)


def _get_bucket(feed_name: str) -> _TokenBucket:
    with _BUCKETS_LOCK:
        bucket = _BUCKETS.get(feed_name)
        if bucket is None:
            bucket = _TokenBucket(_env_limit(feed_name))
            _BUCKETS[feed_name] = bucket
        return bucket


def acquire(feed_name: str) -> None:
    """Block until a token is available for ``feed_name``, then consume it.

    Adapters call this before every outbound HTTP request::

        from alphakit.data.rate_limit import acquire as ratelimit_acquire
        ratelimit_acquire("fred")
        response = fred_client.get(...)
    """
    _get_bucket(feed_name).acquire()


def reset() -> None:
    """Drop every bucket. Test-only helper; not part of the public API."""
    with _BUCKETS_LOCK:
        _BUCKETS.clear()
