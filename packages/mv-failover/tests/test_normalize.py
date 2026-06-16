"""Unit tests for the pure OHLCV normalization (no I/O)."""

from __future__ import annotations

from datetime import datetime, timezone

import polars as pl
import pytest
from mv.failover.smoke.normalize import BARS_COLUMNS, normalize_ohlcv

# Two CCXT-shaped rows: [timestamp_ms, open, high, low, close, volume].
# 2024-01-01T00:00:00Z and 2024-01-01T00:01:00Z.
_ROWS: list[list[float]] = [
    [1_704_067_200_000, 42_000.0, 42_100.0, 41_950.0, 42_080.0, 12.5],
    [1_704_067_260_000, 42_080.0, 42_090.0, 42_000.0, 42_010.0, 9.0],
]


def _normalized() -> pl.DataFrame:
    return normalize_ohlcv(
        _ROWS,
        venue="binance",
        symbol="BTC/USDT",
        timeframe="1m",
        source="ccxt:binance",
    )


def test_columns_and_order() -> None:
    frame = _normalized()
    assert tuple(frame.columns) == BARS_COLUMNS
    assert frame.height == 2


def test_provenance_columns_attached() -> None:
    frame = _normalized()
    assert frame["venue"].to_list() == ["binance", "binance"]
    assert frame["symbol"].unique().to_list() == ["BTC/USDT"]
    assert frame["timeframe"].unique().to_list() == ["1m"]
    assert frame["source"].unique().to_list() == ["ccxt:binance"]


def test_timestamp_is_utc_datetime() -> None:
    frame = _normalized()
    dtype = frame.schema["ts"]
    assert isinstance(dtype, pl.Datetime)
    assert dtype.time_zone == "UTC"
    assert dtype.time_unit == "ms"
    first = frame["ts"][0]
    assert first == datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)


def test_ohlcv_values_are_floats() -> None:
    frame = _normalized()
    for col in ("open", "high", "low", "close", "volume"):
        assert frame.schema[col] == pl.Float64
    assert frame["close"].to_list() == [42_080.0, 42_010.0]


def test_rows_sorted_ascending_by_ts() -> None:
    reversed_rows = list(reversed(_ROWS))
    frame = normalize_ohlcv(
        reversed_rows,
        venue="binance",
        symbol="BTC/USDT",
        timeframe="1m",
        source="ccxt:binance",
    )
    ts = frame["ts"].to_list()
    assert ts == sorted(ts)


def test_empty_rows_raise() -> None:
    with pytest.raises(ValueError, match="no OHLCV rows"):
        normalize_ohlcv([], venue="binance", symbol="BTC/USDT", timeframe="1m", source="x")


def test_malformed_row_raises() -> None:
    bad = [[1_704_067_200_000, 1.0, 2.0, 3.0, 4.0]]  # width 5, not 6
    with pytest.raises(ValueError, match="width 5"):
        normalize_ohlcv(bad, venue="binance", symbol="BTC/USDT", timeframe="1m", source="x")
