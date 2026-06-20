"""Dhan India-equity bar feed (PRD FR-D9) — the India **primary**.

Dhan's historical/intraday charts API returns column-oriented OHLC arrays. The
network call is gated (``# pragma: no cover``); the pure reshape into canonical
OHLCV rows is unit-tested. Credentials are read from ``DHAN_ACCESS_TOKEN`` /
``DHAN_CLIENT_ID`` at call time — never hardcoded (CLAUDE.md #6). Dhan is the
Operator's primary India broker; Upstox → Kotak → Zerodha → Angel One are the
fallbacks on the ``india.prices`` ladder.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import polars as pl
from mv.failover.normalize import normalize_ohlcv

_BASE_URL = "https://api.dhan.co"
_INTERVAL: dict[str, str] = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "1d": "D"}


def candles_to_rows(payload: Mapping[str, Any]) -> list[list[float]]:
    """Reshape a Dhan charts response into ``[ts_ms,o,h,l,c,v]`` rows.

    Dhan returns parallel arrays ``open/high/low/close/volume`` and a
    ``timestamp`` array in **epoch seconds**. Raises ``ValueError`` on a
    malformed payload.
    """
    try:
        times = payload["timestamp"]
        opens, highs, lows, closes, volumes = (
            payload["open"],
            payload["high"],
            payload["low"],
            payload["close"],
            payload["volume"],
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(f"dhan: malformed charts payload: {exc}") from exc
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


class DhanBarFeed:
    """A :class:`~mv.failover.feed.BarFeed` backed by Dhan charts (India primary)."""

    def __init__(self, *, name: str = "dhan", timeout: float = 15.0) -> None:
        self.name = name
        self._timeout = timeout

    def fetch_bars(
        self, symbol: str, timeframe: str, limit: int
    ) -> pl.DataFrame:  # pragma: no cover - network + auth
        import requests

        token = os.environ.get("DHAN_ACCESS_TOKEN")
        client_id = os.environ.get("DHAN_CLIENT_ID")
        if not token or not client_id:
            raise ValueError("dhan: DHAN_ACCESS_TOKEN / DHAN_CLIENT_ID not set")
        headers = {
            "access-token": token,
            "client-id": client_id,
            "Content-Type": "application/json",
        }
        body = {
            "securityId": symbol,
            "exchangeSegment": "NSE_EQ",
            "instrument": "EQUITY",
            "interval": _INTERVAL.get(timeframe, "D"),
        }
        resp = requests.post(
            f"{_BASE_URL}/v2/charts/intraday", json=body, headers=headers, timeout=self._timeout
        )
        resp.raise_for_status()
        rows = candles_to_rows(resp.json())
        return normalize_ohlcv(
            rows, venue="dhan", symbol=symbol, timeframe=timeframe, source=self.name
        )
