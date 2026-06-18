"""Finnhub US-equity bar feed (PRD FR-D9, Phase 6 breadth).

Finnhub stock candles (60 req/min, US real-time via IEX). The network call is
gated (``# pragma: no cover``); the pure reshape from Finnhub's column-oriented
JSON into canonical OHLCV rows is unit-tested. The API key is read from
``FINNHUB_API_KEY`` at call time — never hardcoded (CLAUDE.md #6).
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any

import polars as pl
from mv.failover.normalize import normalize_ohlcv

_BASE_URL = "https://finnhub.io/api/v1"
# Finnhub resolutions keyed by our timeframe vocabulary.
_RESOLUTION: dict[str, str] = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "1d": "D"}


def candles_to_rows(payload: Mapping[str, Any]) -> list[list[float]]:
    """Reshape a Finnhub ``/stock/candle`` response into ``[ts_ms,o,h,l,c,v]`` rows.

    Finnhub returns parallel arrays ``t/o/h/l/c/v`` and a status ``s``; ``t`` is
    in **seconds**. Raises ``ValueError`` on a non-``ok`` or malformed payload.
    """
    if payload.get("s") != "ok":
        raise ValueError(f"finnhub: non-ok candle status: {payload.get('s')!r}")
    try:
        times: Sequence[float] = payload["t"]
        opens, highs, lows, closes, volumes = (
            payload["o"],
            payload["h"],
            payload["l"],
            payload["c"],
            payload["v"],
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(f"finnhub: malformed candle payload: {exc}") from exc
    return [
        [
            float(times[i]) * 1000.0,
            float(opens[i]),
            float(highs[i]),
            float(lows[i]),
            float(closes[i]),
            float(volumes[i]),
        ]
        for i in range(len(times))
    ]


class FinnhubBarFeed:
    """A :class:`~mv.failover.feed.BarFeed` backed by Finnhub stock candles."""

    def __init__(self, *, name: str = "finnhub", timeout: float = 15.0) -> None:
        self.name = name
        self._timeout = timeout

    def fetch_bars(
        self, symbol: str, timeframe: str, limit: int
    ) -> pl.DataFrame:  # pragma: no cover - network
        import time

        import requests

        key = os.environ.get("FINNHUB_API_KEY")
        if not key:
            raise ValueError("finnhub: FINNHUB_API_KEY not set")
        resolution = _RESOLUTION.get(timeframe, "D")
        now = int(time.time())
        params: dict[str, str | int] = {
            "symbol": symbol,
            "resolution": resolution,
            "from": now - limit * _seconds(timeframe),
            "to": now,
            "token": key,
        }
        resp = requests.get(f"{_BASE_URL}/stock/candle", params=params, timeout=self._timeout)
        resp.raise_for_status()
        rows = candles_to_rows(resp.json())
        return normalize_ohlcv(
            rows, venue="finnhub", symbol=symbol, timeframe=timeframe, source=self.name
        )


def _seconds(timeframe: str) -> int:  # pragma: no cover - trivial table
    return {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}.get(timeframe, 86400)
