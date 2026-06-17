"""CCXT-backed crypto bar feed (PRD FR-D9, MVP source).

One adapter per exchange (binance, kraken, coinbase). Public OHLCV endpoints —
no API key. The network call is gated; the normalization it delegates to is
pure and unit-tested in :mod:`mv.failover.normalize`.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from mv.failover.normalize import normalize_ohlcv


class CcxtBarFeed:
    """A :class:`~mv.failover.feed.BarFeed` backed by one CCXT exchange."""

    def __init__(self, exchange_id: str, *, name: str | None = None) -> None:
        self.exchange_id = exchange_id
        self.name = name or f"ccxt:{exchange_id}"
        self._exchange: Any = None

    def _client(self) -> Any:  # pragma: no cover - network client construction
        import ccxt

        if self._exchange is None:
            self._exchange = getattr(ccxt, self.exchange_id)({"enableRateLimit": True})
        return self._exchange

    def fetch_bars(
        self, symbol: str, timeframe: str, limit: int
    ) -> pl.DataFrame:  # pragma: no cover - network
        raw = self._client().fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        rows = [[float(value) for value in row] for row in raw]
        return normalize_ohlcv(
            rows, venue=self.exchange_id, symbol=symbol, timeframe=timeframe, source=self.name
        )
