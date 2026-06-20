"""Upstox India-equity bar feed (PRD FR-D9) — India fallback #1 (after Dhan).

Upstox's historical-candle API returns ``data.candles`` as row arrays with
IST-offset ISO timestamps. The network call is gated (``# pragma: no cover``);
the pure reshape is unit-tested. The token is read from ``UPSTOX_ACCESS_TOKEN``
at call time — never hardcoded.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import polars as pl
from mv.failover.normalize import normalize_ohlcv

_BASE_URL = "https://api.upstox.com/v2"
_INTERVAL: dict[str, str] = {"1m": "1minute", "30m": "30minute", "1d": "day"}


def candles_to_rows(payload: Mapping[str, Any]) -> list[list[float]]:
    """Reshape an Upstox ``/historical-candle`` response into ``[ts_ms,o,h,l,c,v]`` rows.

    ``payload['data']['candles']`` is a list of ``[iso_ts, o, h, l, c, v, oi]``.
    Raises ``ValueError`` on a non-success status or malformed payload.
    """
    if payload.get("status") not in (None, "success"):
        raise ValueError(f"upstox: non-success status: {payload.get('status')!r}")
    try:
        candles = payload["data"]["candles"]
        return [
            [
                datetime.fromisoformat(row[0]).timestamp() * 1000.0,
                float(row[1]),
                float(row[2]),
                float(row[3]),
                float(row[4]),
                float(row[5]),
            ]
            for row in candles
        ]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError(f"upstox: malformed candle payload: {exc}") from exc


class UpstoxBarFeed:
    """A :class:`~mv.failover.feed.BarFeed` backed by Upstox historical candles."""

    def __init__(self, *, name: str = "upstox", timeout: float = 15.0) -> None:
        self.name = name
        self._timeout = timeout

    def fetch_bars(
        self, symbol: str, timeframe: str, limit: int
    ) -> pl.DataFrame:  # pragma: no cover - network + auth
        import requests

        token = os.environ.get("UPSTOX_ACCESS_TOKEN")
        if not token:
            raise ValueError("upstox: UPSTOX_ACCESS_TOKEN not set")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        interval = _INTERVAL.get(timeframe, "day")
        resp = requests.get(
            f"{_BASE_URL}/historical-candle/{symbol}/{interval}",
            headers=headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        rows = candles_to_rows(resp.json())
        return normalize_ohlcv(
            rows, venue="upstox", symbol=symbol, timeframe=timeframe, source=self.name
        )
