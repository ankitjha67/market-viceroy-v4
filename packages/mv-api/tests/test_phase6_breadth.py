"""FR-S5 / US-009: a catalog strategy runs on governor-served US-equity bars.

Proves "breadth grows without rearchitecting": the same `StrategyProtocol` and
the same Failover Governor serve a US-equity symbol via the new adapter slot —
no parallel data path, no strategy change. Offline (a fake feed stands in for
Finnhub/Alpaca; live fetch is gated).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import polars as pl
from alphakit.strategies.trend.sma_cross_10_30 import SMACross1030
from mv.failover.events import CollectingSink
from mv.failover.normalize import normalize_ohlcv
from mv.failover.registry import US_PRICES, LadderRegistry, SourceSpec
from mv.failover.router import DataSourceRouter

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _FakeUsFeed:
    name = "finnhub"

    def __init__(self, frame: pl.DataFrame) -> None:
        self._frame = frame

    def fetch_bars(self, symbol: str, timeframe: str, limit: int) -> pl.DataFrame:
        return self._frame


def _bars(n: int = 40) -> pl.DataFrame:
    rows = []
    price = 100.0
    for i in range(n):
        price *= 1.01
        ts_ms = int((_T0 + timedelta(days=i)).timestamp() * 1000)
        rows.append([ts_ms, price, price, price, price, 1000.0])
    return normalize_ohlcv(rows, venue="finnhub", symbol="AAPL", timeframe="1d", source="finnhub")


def test_catalog_strategy_runs_on_governor_us_bars() -> None:
    registry = LadderRegistry()
    registry.register(
        US_PRICES, [SourceSpec(name="finnhub", priority=0, feed=_FakeUsFeed(_bars()))]
    )
    # Clock at the last bar so the served frame is fresh (no staleness failover).
    last = _T0 + timedelta(days=39)
    router = DataSourceRouter(registry, event_sink=CollectingSink(), clock=lambda: last)

    result = router.get_bars(US_PRICES, "AAPL", "1d")
    assert result.source == "finnhub"

    # Convert the governor's canonical bars into the pandas panel a StrategyProtocol
    # consumes — the same seam the crypto loop uses, now on a US symbol.
    frame = result.frame.sort("ts")
    panel = pd.DataFrame(
        {"AAPL": frame["close"].to_list()},
        index=pd.DatetimeIndex(frame["ts"].to_list()),
    )
    weights = SMACross1030().generate_signals(panel)
    assert "AAPL" in weights.columns
    assert len(weights) == len(panel)
