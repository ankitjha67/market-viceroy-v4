"""Pure helpers for the Command Deck price chart: OHLCV candles + trade markers.

Turns the loop's INR OHLCV frame and journaled fills into the lightweight-charts
shapes the UI renders — epoch-second candles, a volume series, and BUY/SELL
markers at the bars where orders filled — so the deck shows the actual price the
strategies traded, with our entries/exits on it. Pure / deterministic, no I/O.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import polars as pl

_BAR_COLUMNS = ("ts", "open", "high", "low", "close", "volume")


def ohlcv_bars(frame: pl.DataFrame, *, max_bars: int = 500) -> list[dict[str, Any]]:
    """The last ``max_bars`` rows of ``frame`` as chart candles (epoch-second time).

    Empty (or a frame missing OHLCV columns) yields ``[]`` rather than raising, so
    a cold loop renders an empty chart instead of erroring.
    """
    if frame.height == 0 or not set(_BAR_COLUMNS) <= set(frame.columns):
        return []
    tail = frame.tail(max_bars)
    times = tail.get_column("ts").dt.epoch(time_unit="s").to_list()
    rows = tail.select(_BAR_COLUMNS[1:]).rows()  # (open, high, low, close, volume)
    return [
        {
            "time": int(t),
            "open": float(o),
            "high": float(h),
            "low": float(low),
            "close": float(c),
            "volume": float(v),
        }
        for t, (o, h, low, c, v) in zip(times, rows, strict=True)
    ]


def _epoch_seconds(iso: str) -> int | None:
    try:
        return int(datetime.fromisoformat(iso).timestamp())
    except (ValueError, TypeError):
        return None


def fill_markers(executions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """BUY/SELL markers at the bar each fill happened, from execution payloads.

    Reads the ``bar_ts`` the loop stamps on each fill (the bar time, not the
    journal wall-clock), so markers land on the candle that traded. Entries
    without a usable ``bar_ts`` are skipped.
    """
    markers: list[dict[str, Any]] = []
    for payload in executions:
        bar_ts = payload.get("bar_ts")
        if not isinstance(bar_ts, str):
            continue
        seconds = _epoch_seconds(bar_ts)
        if seconds is None:
            continue
        markers.append(
            {
                "time": seconds,
                "side": str(payload.get("side", "")),
                "price": str(payload.get("price", "0")),
            }
        )
    return markers


def chart_payload(
    frame: pl.DataFrame, executions: list[dict[str, Any]], *, max_bars: int = 500
) -> dict[str, Any]:
    """The full price-chart payload: INR candles + volume + trade markers."""
    return {"bars": ohlcv_bars(frame, max_bars=max_bars), "markers": fill_markers(executions)}


__all__ = ["chart_payload", "fill_markers", "ohlcv_bars"]
