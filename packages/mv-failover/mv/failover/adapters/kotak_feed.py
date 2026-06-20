"""Kotak Securities (Neo) India-equity bar feed (PRD FR-D9) — India fallback #2.

Kotak's Neo API returns historical candles as row arrays. The network call is
gated (``# pragma: no cover``); the pure reshape is unit-tested. Credentials are
read from ``KOTAK_ACCESS_TOKEN`` / ``KOTAK_CONSUMER_KEY`` at call time — never
hardcoded.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import polars as pl
from mv.failover.normalize import normalize_ohlcv

_BASE_URL = "https://gw-napi.kotaksecurities.com"
_INTERVAL: dict[str, str] = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "1d": "D"}


def candles_to_rows(payload: Mapping[str, Any]) -> list[list[float]]:
    """Reshape a Kotak Neo candles response into ``[ts_ms,o,h,l,c,v]`` rows.

    ``payload['data']`` is a list of ``[iso_ts, o, h, l, c, v]`` rows. Raises
    ``ValueError`` on a malformed payload.
    """
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError("kotak: payload missing 'data'")
    try:
        return [
            [
                datetime.fromisoformat(str(row[0])).timestamp() * 1000.0,
                float(row[1]),
                float(row[2]),
                float(row[3]),
                float(row[4]),
                float(row[5]),
            ]
            for row in data
        ]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError(f"kotak: malformed candle payload: {exc}") from exc


class KotakBarFeed:
    """A :class:`~mv.failover.feed.BarFeed` backed by Kotak Neo historical candles."""

    def __init__(self, *, name: str = "kotak", timeout: float = 15.0) -> None:
        self.name = name
        self._timeout = timeout

    def fetch_bars(
        self, symbol: str, timeframe: str, limit: int
    ) -> pl.DataFrame:  # pragma: no cover - network + auth
        import requests

        token = os.environ.get("KOTAK_ACCESS_TOKEN")
        consumer = os.environ.get("KOTAK_CONSUMER_KEY")
        if not token or not consumer:
            raise ValueError("kotak: KOTAK_ACCESS_TOKEN / KOTAK_CONSUMER_KEY not set")
        headers = {"Authorization": f"Bearer {token}", "consumerKey": consumer}
        params = {"symbol": symbol, "interval": _INTERVAL.get(timeframe, "D"), "exchange": "NSE"}
        resp = requests.get(
            f"{_BASE_URL}/quotes/v1/ohlc/historical",
            params=params,
            headers=headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        rows = candles_to_rows(resp.json())
        return normalize_ohlcv(
            rows, venue="kotak", symbol=symbol, timeframe=timeframe, source=self.name
        )
