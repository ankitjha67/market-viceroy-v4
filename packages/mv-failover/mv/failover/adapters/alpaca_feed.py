"""Alpaca US-equity bar feed (PRD FR-D9, Phase 6 breadth).

Alpaca market-data bars (paper/broker; the US fallback below Finnhub). The
network call is gated (``# pragma: no cover``); the pure reshape from Alpaca's
row-oriented JSON into canonical OHLCV rows is unit-tested. Credentials are read
from ``ALPACA_API_KEY`` / ``ALPACA_API_SECRET`` at call time (CLAUDE.md #6).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import polars as pl
from mv.failover.normalize import normalize_ohlcv

_BASE_URL = "https://data.alpaca.markets/v2"
_TIMEFRAME: dict[str, str] = {
    "1m": "1Min",
    "5m": "5Min",
    "15m": "15Min",
    "1h": "1Hour",
    "1d": "1Day",
}


def _iso_to_ms(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000.0


def bars_to_rows(payload: Mapping[str, Any]) -> list[list[float]]:
    """Reshape an Alpaca ``/bars`` response into ``[ts_ms,o,h,l,c,v]`` rows.

    Each bar is ``{t,o,h,l,c,v}`` with ``t`` an RFC-3339 timestamp. Raises
    ``ValueError`` on a malformed payload.
    """
    bars = payload.get("bars")
    if bars is None:
        raise ValueError("alpaca: payload missing 'bars'")
    try:
        return [
            [
                _iso_to_ms(bar["t"]),
                float(bar["o"]),
                float(bar["h"]),
                float(bar["l"]),
                float(bar["c"]),
                float(bar["v"]),
            ]
            for bar in bars
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"alpaca: malformed bars payload: {exc}") from exc


class AlpacaBarFeed:
    """A :class:`~mv.failover.feed.BarFeed` backed by Alpaca market data."""

    def __init__(self, *, name: str = "alpaca", timeout: float = 15.0) -> None:
        self.name = name
        self._timeout = timeout

    def fetch_bars(
        self, symbol: str, timeframe: str, limit: int
    ) -> pl.DataFrame:  # pragma: no cover - network
        import requests

        key = os.environ.get("ALPACA_API_KEY")
        secret = os.environ.get("ALPACA_API_SECRET")
        if not key or not secret:
            raise ValueError("alpaca: ALPACA_API_KEY / ALPACA_API_SECRET not set")
        headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        params: dict[str, str | int] = {
            "timeframe": _TIMEFRAME.get(timeframe, "1Day"),
            "limit": limit,
        }
        resp = requests.get(
            f"{_BASE_URL}/stocks/{symbol}/bars",
            params=params,
            headers=headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        rows = bars_to_rows(resp.json())
        return normalize_ohlcv(
            rows, venue="alpaca", symbol=symbol, timeframe=timeframe, source=self.name
        )
