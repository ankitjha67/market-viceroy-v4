"""Zerodha (Kite Connect) India-equity bar feed (PRD FR-D9) — India fallback #3.

Kite's historical-data API returns ``data.candles`` as row arrays with IST-offset
ISO timestamps. The network call is gated (``# pragma: no cover``); the pure
reshape is unit-tested. Credentials are read from ``ZERODHA_API_KEY`` /
``ZERODHA_ACCESS_TOKEN`` at call time — never hardcoded. NOTE: Kite **prohibits
redistribution** of its data — this feed is internal-use only (§13).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import polars as pl
from mv.failover.normalize import normalize_ohlcv

_BASE_URL = "https://api.kite.trade"
_INTERVAL: dict[str, str] = {"1m": "minute", "5m": "5minute", "15m": "15minute", "1d": "day"}


def candles_to_rows(payload: Mapping[str, Any]) -> list[list[float]]:
    """Reshape a Kite ``/instruments/historical`` response into ``[ts_ms,o,h,l,c,v]`` rows.

    ``payload['data']['candles']`` is a list of ``[iso_ts, o, h, l, c, v]``.
    Raises ``ValueError`` on a non-success status or malformed payload.
    """
    if payload.get("status") not in (None, "success"):
        raise ValueError(f"zerodha: non-success status: {payload.get('status')!r}")
    try:
        candles = payload["data"]["candles"]
        return [
            [
                datetime.fromisoformat(str(row[0])).timestamp() * 1000.0,
                float(row[1]),
                float(row[2]),
                float(row[3]),
                float(row[4]),
                float(row[5]),
            ]
            for row in candles
        ]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError(f"zerodha: malformed candle payload: {exc}") from exc


class ZerodhaBarFeed:
    """A :class:`~mv.failover.feed.BarFeed` backed by Zerodha Kite (internal-use only)."""

    def __init__(self, *, name: str = "zerodha", timeout: float = 15.0) -> None:
        self.name = name
        self._timeout = timeout

    def fetch_bars(
        self, symbol: str, timeframe: str, limit: int
    ) -> pl.DataFrame:  # pragma: no cover - network + auth
        import requests

        api_key = os.environ.get("ZERODHA_API_KEY")
        token = os.environ.get("ZERODHA_ACCESS_TOKEN")
        if not api_key or not token:
            raise ValueError("zerodha: ZERODHA_API_KEY / ZERODHA_ACCESS_TOKEN not set")
        headers = {"Authorization": f"token {api_key}:{token}", "X-Kite-Version": "3"}
        interval = _INTERVAL.get(timeframe, "day")
        resp = requests.get(
            f"{_BASE_URL}/instruments/historical/{symbol}/{interval}",
            headers=headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        rows = candles_to_rows(resp.json())
        return normalize_ohlcv(
            rows, venue="zerodha", symbol=symbol, timeframe=timeframe, source=self.name
        )
