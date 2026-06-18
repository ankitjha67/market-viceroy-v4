"""Angel One SmartAPI India-equity bar feed (PRD FR-D9, Phase 6 breadth).

Angel One SmartAPI is the India Tier-1 primary (free, full hist + live;
NSE/BSE/NFO/...). The network call (auth + candle fetch) is gated
(``# pragma: no cover``); the pure reshape from SmartAPI's row-oriented JSON
into canonical OHLCV rows is unit-tested. Credentials are read from env at call
time (CLAUDE.md #6). The India pre-open strategies + nse-market-intel research
agent (the four private repos) are folded in once the Operator shares them —
this adapter is the data contract they plug into.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import polars as pl
from mv.failover.normalize import normalize_ohlcv

_BASE_URL = "https://apiconnect.angelbroking.com"
_INTERVAL: dict[str, str] = {
    "1m": "ONE_MINUTE",
    "5m": "FIVE_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "1h": "ONE_HOUR",
    "1d": "ONE_DAY",
}


def candles_to_rows(payload: Mapping[str, Any]) -> list[list[float]]:
    """Reshape a SmartAPI ``getCandleData`` response into ``[ts_ms,o,h,l,c,v]`` rows.

    ``payload['data']`` is a list of ``[iso_ts, o, h, l, c, v]`` rows (IST-offset
    timestamps). Raises ``ValueError`` on a non-true status or malformed payload.
    """
    if not payload.get("status", False):
        raise ValueError(f"angelone: non-true status: {payload.get('message')!r}")
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError("angelone: payload missing 'data'")
    try:
        return [
            [
                datetime.fromisoformat(row[0]).timestamp() * 1000.0,
                float(row[1]),
                float(row[2]),
                float(row[3]),
                float(row[4]),
                float(row[5]),
            ]
            for row in data
        ]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError(f"angelone: malformed candle payload: {exc}") from exc


class AngelOneBarFeed:
    """A :class:`~mv.failover.feed.BarFeed` backed by Angel One SmartAPI candles."""

    def __init__(self, *, name: str = "angelone", timeout: float = 15.0) -> None:
        self.name = name
        self._timeout = timeout

    def fetch_bars(
        self, symbol: str, timeframe: str, limit: int
    ) -> pl.DataFrame:  # pragma: no cover - network + auth
        import requests

        key = os.environ.get("ANGELONE_API_KEY")
        token = os.environ.get("ANGELONE_ACCESS_TOKEN")
        if not key or not token:
            raise ValueError("angelone: ANGELONE_API_KEY / ANGELONE_ACCESS_TOKEN not set")
        headers = {"X-PrivateKey": key, "Authorization": f"Bearer {token}"}
        body = {
            "exchange": "NSE",
            "symboltoken": symbol,
            "interval": _INTERVAL.get(timeframe, "ONE_DAY"),
        }
        resp = requests.post(
            f"{_BASE_URL}/rest/secure/angelbroking/historical/v1/getCandleData",
            json=body,
            headers=headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        rows = candles_to_rows(resp.json())
        return normalize_ohlcv(
            rows, venue="angelone", symbol=symbol, timeframe=timeframe, source=self.name
        )
