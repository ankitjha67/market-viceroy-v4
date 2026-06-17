"""Cache-aside for bars: Redis hot (latest) + ClickHouse warm (history).

Serve fresh cache before spending a provider's quota (PRD FR-D6). The key
derivation is pure (unit-tested); the Redis/ClickHouse calls are gated I/O
exercised by the CI integration job.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl
from mv.failover.normalize import BARS_COLUMNS

if TYPE_CHECKING:
    import clickhouse_connect.driver
    import redis as redis_lib


def latest_key(symbol: str, timeframe: str) -> str:
    """Redis key for the latest cached bar of ``symbol``/``timeframe``."""
    return f"bars:latest:{symbol}:{timeframe}"


class BarCache:
    """Redis hot cache + ClickHouse warm store for normalized bars."""

    def __init__(
        self,
        redis_client: redis_lib.Redis,
        clickhouse_client: clickhouse_connect.driver.Client,
        *,
        hot_ttl_seconds: int = 120,
    ) -> None:
        self._redis = redis_client
        self._clickhouse = clickhouse_client
        self._hot_ttl = hot_ttl_seconds

    def cache_latest(
        self, symbol: str, timeframe: str, frame: pl.DataFrame
    ) -> None:  # pragma: no cover - I/O
        """Cache the most recent bar (as JSON) in Redis with a short TTL."""
        latest = frame.sort("ts").tail(1).write_json()
        self._redis.set(latest_key(symbol, timeframe), latest, ex=self._hot_ttl)

    def read_cached_latest(
        self, symbol: str, timeframe: str
    ) -> pl.DataFrame | None:  # pragma: no cover - I/O
        """Return the cached latest bar, or None on a miss."""
        raw = self._redis.get(latest_key(symbol, timeframe))
        if raw is None:
            return None
        return pl.read_json(raw.encode() if isinstance(raw, str) else raw)

    def write_bars(self, frame: pl.DataFrame) -> int:  # pragma: no cover - I/O
        """Write bars to the ClickHouse warm store; return rows written."""
        self._clickhouse.insert("bars", frame.rows(), column_names=list(BARS_COLUMNS))
        return frame.height
