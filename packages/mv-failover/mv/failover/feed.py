"""The bar-feed contract every crypto source adapter implements."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import polars as pl


@runtime_checkable
class BarFeed(Protocol):
    """A source that returns recent OHLCV bars as a normalized Polars frame.

    Implementations normalize to the canonical bars schema
    (:data:`mv.failover.normalize.BARS_COLUMNS`) so the router can treat every
    source identically.
    """

    name: str
    """Source id, e.g. ``"ccxt:binance"``."""

    def fetch_bars(self, symbol: str, timeframe: str, limit: int) -> pl.DataFrame:
        """Return up to ``limit`` recent bars for ``symbol`` at ``timeframe``."""
        ...
