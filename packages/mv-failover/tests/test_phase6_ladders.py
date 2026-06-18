"""Tests for the Phase-6 breadth ladders + governed failover across new domains."""

from __future__ import annotations

from datetime import datetime, timezone

import polars as pl
from mv.failover.events import CollectingSink
from mv.failover.ladders import build_default_registry
from mv.failover.normalize import normalize_ohlcv
from mv.failover.registry import CRYPTO_PRICES, FX_RATES, INDIA_PRICES, US_PRICES, SourceSpec
from mv.failover.router import DataSourceRouter

_T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_default_registry_registers_breadth_domains() -> None:
    registry = build_default_registry()
    domains = set(registry.domains())
    assert {CRYPTO_PRICES, US_PRICES, INDIA_PRICES, FX_RATES} <= domains


def test_us_ladder_is_finnhub_then_alpaca() -> None:
    ladder = build_default_registry().ladder(US_PRICES)
    assert [s.name for s in ladder] == ["finnhub", "alpaca"]
    assert [s.priority for s in ladder] == [0, 1]


def test_fx_source_is_redistribution_safe() -> None:
    [fx] = build_default_registry().ladder(FX_RATES)
    assert fx.name == "frankfurter"
    assert fx.licensing_tag == "redistribution-safe"


class _FakeFeed:
    def __init__(
        self, name: str, *, frame: pl.DataFrame | None = None, error: Exception | None = None
    ) -> None:
        self.name = name
        self._frame = frame
        self._error = error
        self.calls = 0

    def fetch_bars(self, symbol: str, timeframe: str, limit: int) -> pl.DataFrame:
        self.calls += 1
        if self._error is not None:
            raise self._error
        assert self._frame is not None
        return self._frame


def _frame(source: str) -> pl.DataFrame:
    rows = [[int(_T0.timestamp() * 1000), 100.0, 100.0, 100.0, 100.0, 1.0]]
    return normalize_ohlcv(rows, venue="x", symbol="AAPL", timeframe="1h", source=source)


def test_us_domain_fails_over_finnhub_to_alpaca() -> None:
    # Breadth grows without rearchitecting: the same governor failover works on
    # a US-equity domain with the new adapters swapped for fakes.
    from mv.failover.registry import LadderRegistry

    finnhub = _FakeFeed("finnhub", error=ConnectionError("429"))
    alpaca = _FakeFeed("alpaca", frame=_frame("alpaca"))
    registry = LadderRegistry()
    registry.register(
        US_PRICES,
        [
            SourceSpec(name="finnhub", priority=0, feed=finnhub),
            SourceSpec(name="alpaca", priority=1, feed=alpaca),
        ],
    )
    sink = CollectingSink()
    router = DataSourceRouter(registry, event_sink=sink, clock=lambda: _T0)
    result = router.get_bars(US_PRICES, "AAPL", "1h")
    assert result.source == "alpaca"
    assert len(result.failovers) == 1
    assert result.failovers[0].from_source == "finnhub"
