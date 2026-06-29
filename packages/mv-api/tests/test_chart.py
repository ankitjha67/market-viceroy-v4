"""Tests for the pure price-chart helpers (mv.api.chart)."""

from __future__ import annotations

import polars as pl
from mv.api.chart import chart_payload, fill_markers, ohlcv_bars
from mv.failover.normalize import normalize_ohlcv

_HOUR_MS = 3_600_000
_BASE_MS = 1_704_067_200_000  # 2024-01-01T00:00:00Z
_BASE_S = _BASE_MS // 1000


def _frame(n: int = 5) -> pl.DataFrame:
    rows = [
        [_BASE_MS + i * _HOUR_MS, 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 10.0 + i]
        for i in range(n)
    ]
    return normalize_ohlcv(
        rows, venue="binance", symbol="BTC/USDT", timeframe="1h", source="ccxt:binance"
    )


def test_ohlcv_bars_shape_and_epoch_seconds() -> None:
    bars = ohlcv_bars(_frame(3))
    assert len(bars) == 3
    first = bars[0]
    assert set(first) == {"time", "open", "high", "low", "close", "volume"}
    assert first["time"] == _BASE_S  # ms epoch -> seconds
    assert first["open"] == 100.0 and first["close"] == 100.5


def test_ohlcv_bars_caps_to_max_keeping_the_latest() -> None:
    bars = ohlcv_bars(_frame(10), max_bars=4)
    assert len(bars) == 4
    assert bars[-1]["time"] == _BASE_S + 9 * 3600  # the most recent bar


def test_ohlcv_bars_empty_frame_is_empty() -> None:
    assert ohlcv_bars(pl.DataFrame()) == []


def test_fill_markers_from_executions_skips_missing_bar_ts() -> None:
    execs = [
        {"side": "BUY", "price": "100.5", "bar_ts": "2024-01-01T00:00:00+00:00"},
        {"side": "SELL", "price": "110.0", "bar_ts": "2024-01-01T01:00:00+00:00"},
        {"side": "BUY", "price": "1"},  # no bar_ts -> skipped
    ]
    markers = fill_markers(execs)
    assert len(markers) == 2
    assert markers[0] == {"time": _BASE_S, "side": "BUY", "price": "100.5"}
    assert markers[1]["side"] == "SELL"


def test_chart_payload_combines_bars_and_markers() -> None:
    out = chart_payload(
        _frame(3),
        [{"side": "BUY", "price": "100.5", "bar_ts": "2024-01-01T00:00:00+00:00"}],
    )
    assert len(out["bars"]) == 3
    assert len(out["markers"]) == 1
