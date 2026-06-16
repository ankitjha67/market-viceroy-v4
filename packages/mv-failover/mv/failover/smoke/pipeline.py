"""I/O glue for the Phase-0 smoke: CCXT fetch, ClickHouse write + read-back.

Every function here touches the network or the database, so they are marked
``# pragma: no cover`` for the unit-coverage gate and are instead exercised by
the CI integration job (against a ClickHouse service container) and by
``uv run mv-smoke`` locally. The pure transform they wrap lives in
:mod:`mv.failover.smoke.normalize` and is fully unit-tested.
"""

from __future__ import annotations

from dataclasses import dataclass

import ccxt
import clickhouse_connect
import polars as pl
from mv.failover.smoke.config import SmokeSettings
from mv.failover.smoke.normalize import BARS_COLUMNS, normalize_ohlcv


@dataclass(frozen=True, slots=True)
class RoundTrip:
    """Outcome of a smoke round-trip."""

    venue: str
    symbol: str
    timeframe: str
    written: int
    read_back: int

    @property
    def ok(self) -> bool:
        """True when at least the rows we wrote are readable back."""
        return self.written > 0 and self.read_back >= self.written


def fetch_ohlcv(settings: SmokeSettings) -> list[list[float]]:  # pragma: no cover - network I/O
    """Fetch recent OHLCV bars for the configured symbol via a public CCXT feed."""
    exchange_cls = getattr(ccxt, settings.smoke_exchange)
    exchange = exchange_cls({"enableRateLimit": True})
    raw = exchange.fetch_ohlcv(
        settings.smoke_symbol,
        timeframe=settings.smoke_timeframe,
        limit=settings.smoke_limit,
    )
    return [[float(value) for value in row] for row in raw]


def _client(
    settings: SmokeSettings,
) -> clickhouse_connect.driver.Client:  # pragma: no cover - DB I/O
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_http_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_db,
    )


def write_bars(frame: pl.DataFrame, settings: SmokeSettings) -> int:  # pragma: no cover - DB I/O
    """Insert the normalized bars frame into ClickHouse; return rows written."""
    client = _client(settings)
    try:
        client.insert(
            "bars",
            frame.rows(),
            column_names=list(BARS_COLUMNS),
        )
    finally:
        client.close()
    return frame.height


def count_bars(settings: SmokeSettings) -> int:  # pragma: no cover - DB I/O
    """Count stored bars for the configured symbol + timeframe."""
    client = _client(settings)
    try:
        result = client.query(
            "SELECT count() FROM bars WHERE symbol = %(symbol)s AND timeframe = %(timeframe)s",
            parameters={
                "symbol": settings.smoke_symbol,
                "timeframe": settings.smoke_timeframe,
            },
        )
        return int(result.result_rows[0][0])
    finally:
        client.close()


def run_smoke(settings: SmokeSettings) -> RoundTrip:  # pragma: no cover - integration I/O
    """Run the full data-pipe round-trip and return its outcome."""
    rows = fetch_ohlcv(settings)
    frame = normalize_ohlcv(
        rows,
        venue=settings.smoke_exchange,
        symbol=settings.smoke_symbol,
        timeframe=settings.smoke_timeframe,
        source=f"ccxt:{settings.smoke_exchange}",
    )
    written = write_bars(frame, settings)
    read_back = count_bars(settings)
    return RoundTrip(
        venue=settings.smoke_exchange,
        symbol=settings.smoke_symbol,
        timeframe=settings.smoke_timeframe,
        written=written,
        read_back=read_back,
    )
