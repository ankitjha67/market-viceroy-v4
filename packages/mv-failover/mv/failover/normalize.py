"""Pure, deterministic normalization of CCXT OHLCV rows into canonical bars.

No I/O, no clock, no network — trivially unit-testable. Shared by every crypto
source adapter and the governor so all sources normalize to one schema.
"""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl

# Canonical bars schema, in ClickHouse insert order (see
# infra/clickhouse/init/01_bars.sql). ``ingested_at`` is DB-defaulted.
BARS_COLUMNS: tuple[str, ...] = (
    "venue",
    "symbol",
    "ts",
    "timeframe",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "source",
)

# CCXT fetch_ohlcv rows are [timestamp_ms, open, high, low, close, volume].
_OHLCV_WIDTH = 6


def normalize_ohlcv(
    rows: Sequence[Sequence[float]],
    *,
    venue: str,
    symbol: str,
    timeframe: str,
    source: str,
) -> pl.DataFrame:
    """Normalize raw CCXT OHLCV rows into the canonical bars frame.

    Each input row is ``[timestamp_ms, open, high, low, close, volume]`` as
    returned by ``ccxt.Exchange.fetch_ohlcv``. The millisecond epoch is
    converted to a UTC ``Datetime`` and the provenance columns
    (``venue``/``symbol``/``timeframe``/``source``) are attached.

    Args:
        rows: Sequence of OHLCV rows, each of length 6.
        venue: Exchange id (e.g. ``"binance"``).
        symbol: Unified symbol (e.g. ``"BTC/USDT"``).
        timeframe: Bar timeframe (e.g. ``"1m"``).
        source: Adapter/provenance tag recorded on every row.

    Returns:
        A Polars frame with columns :data:`BARS_COLUMNS`, ``ts`` as a
        UTC-aware millisecond ``Datetime``, sorted ascending by ``ts``.

    Raises:
        ValueError: If ``rows`` is empty or any row is not length 6.
    """
    if not rows:
        raise ValueError("no OHLCV rows to normalize")
    for i, row in enumerate(rows):
        if len(row) != _OHLCV_WIDTH:
            raise ValueError(f"OHLCV row {i} has width {len(row)}, expected {_OHLCV_WIDTH}")

    n = len(rows)
    # Millisecond precision throughout, to match the ClickHouse
    # DateTime64(3, 'UTC') storage column exactly.
    ts = (
        pl.from_epoch(pl.Series("ts", [int(row[0]) for row in rows]), time_unit="ms")
        .dt.cast_time_unit("ms")
        .dt.replace_time_zone("UTC")
    )

    frame = pl.DataFrame(
        {
            "venue": [venue] * n,
            "symbol": [symbol] * n,
            "ts": ts,
            "timeframe": [timeframe] * n,
            "open": [float(row[1]) for row in rows],
            "high": [float(row[2]) for row in rows],
            "low": [float(row[3]) for row in rows],
            "close": [float(row[4]) for row in rows],
            "volume": [float(row[5]) for row in rows],
            "source": [source] * n,
        }
    )
    return frame.select(BARS_COLUMNS).sort("ts")
