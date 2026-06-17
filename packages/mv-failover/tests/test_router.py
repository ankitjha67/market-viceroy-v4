"""Router tests — demonstrates US-003: seamless failover + reconciliation halt."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import polars as pl
import pytest
from mv.failover.circuit_breaker import CircuitBreaker
from mv.failover.errors import NoHealthySourceError, ReconciliationError
from mv.failover.events import CollectingSink
from mv.failover.health import HealthStatus
from mv.failover.normalize import normalize_ohlcv
from mv.failover.registry import CRYPTO_PRICES, LadderRegistry, SourceSpec
from mv.failover.router import DataSourceRouter

_T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _frame(
    latest_ts: datetime, *, close: float = 100.0, source: str = "ccxt:binance"
) -> pl.DataFrame:
    rows = [[int(latest_ts.timestamp() * 1000), close, close, close, close, 1.0]]
    return normalize_ohlcv(rows, venue="x", symbol="BTC/USDT", timeframe="1h", source=source)


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


def _registry(*feeds: _FakeFeed) -> LadderRegistry:
    registry = LadderRegistry()
    registry.register(
        CRYPTO_PRICES,
        [SourceSpec(name=f.name, priority=i, feed=f) for i, f in enumerate(feeds)],
    )
    return registry


def _router(
    registry: LadderRegistry, sink: CollectingSink, *, now: datetime = _T0
) -> DataSourceRouter:
    return DataSourceRouter(registry, event_sink=sink, clock=lambda: now)


def test_serves_primary_no_failover() -> None:
    primary = _FakeFeed("binance", frame=_frame(_T0))
    secondary = _FakeFeed("kraken", frame=_frame(_T0))
    sink = CollectingSink()
    result = _router(_registry(primary, secondary), sink).get_bars(CRYPTO_PRICES, "BTC/USDT", "1h")
    assert result.source == "binance"
    assert result.failovers == []
    assert secondary.calls == 0
    assert sink.failovers == []


def test_failover_when_primary_errors() -> None:
    primary = _FakeFeed("binance", error=ConnectionError("429"))
    secondary = _FakeFeed("kraken", frame=_frame(_T0, source="ccxt:kraken"))
    sink = CollectingSink()
    result = _router(_registry(primary, secondary), sink).get_bars(CRYPTO_PRICES, "BTC/USDT", "1h")
    # Failed over to the fallback within the one call (one bar), switch logged.
    assert result.source == "kraken"
    assert len(result.failovers) == 1
    assert result.failovers[0].from_source == "binance"
    assert result.failovers[0].to_source == "kraken"
    assert len(sink.failovers) == 1


def test_failover_when_primary_stale() -> None:
    stale = _FakeFeed("binance", frame=_frame(_T0 - timedelta(hours=10)))
    fresh = _FakeFeed("kraken", frame=_frame(_T0, source="ccxt:kraken"))
    sink = CollectingSink()
    result = _router(_registry(stale, fresh), sink).get_bars(CRYPTO_PRICES, "BTC/USDT", "1h")
    assert result.source == "kraken"
    assert result.failovers[0].from_source == "binance"


def test_open_breaker_skips_source_without_calling_it() -> None:
    primary = _FakeFeed("binance", error=ConnectionError("down"))
    secondary = _FakeFeed("kraken", frame=_frame(_T0, source="ccxt:kraken"))
    sink = CollectingSink()
    router = DataSourceRouter(
        _registry(primary, secondary),
        event_sink=sink,
        clock=lambda: _T0,
        breaker_factory=lambda: CircuitBreaker(failure_threshold=2, recovery_timeout=1000),
    )
    # Two failures open binance's breaker.
    router.get_bars(CRYPTO_PRICES, "BTC/USDT", "1h")
    router.get_bars(CRYPTO_PRICES, "BTC/USDT", "1h")
    assert primary.calls == 2
    # Third call: breaker open -> binance skipped without a fetch, kraken serves.
    result = router.get_bars(CRYPTO_PRICES, "BTC/USDT", "1h")
    assert primary.calls == 2  # not called again
    assert result.source == "kraken"


def test_all_sources_fail_raises() -> None:
    a = _FakeFeed("binance", error=ConnectionError("a"))
    b = _FakeFeed("kraken", error=ConnectionError("b"))
    sink = CollectingSink()
    with pytest.raises(NoHealthySourceError):
        _router(_registry(a, b), sink).get_bars(CRYPTO_PRICES, "BTC/USDT", "1h")


def test_health_reflects_failover() -> None:
    primary = _FakeFeed("binance", error=ConnectionError("x"))
    secondary = _FakeFeed("kraken", frame=_frame(_T0, source="ccxt:kraken"))
    sink = CollectingSink()
    router = _router(_registry(primary, secondary), sink)
    router.get_bars(CRYPTO_PRICES, "BTC/USDT", "1h")
    assert router.health.snapshot("binance").status is HealthStatus.RED
    assert router.health.snapshot("kraken").status is HealthStatus.GREEN


# --- reconciliation (BR-002) ---------------------------------------------


def test_reconciled_agreement_returns_primary() -> None:
    a = _FakeFeed("binance", frame=_frame(_T0, close=100.0, source="ccxt:binance"))
    b = _FakeFeed("kraken", frame=_frame(_T0, close=100.2, source="ccxt:kraken"))
    sink = CollectingSink()
    result = _router(_registry(a, b), sink).get_bars_reconciled(
        CRYPTO_PRICES, "BTC/USDT", "1h", tolerance=0.005
    )
    assert result.source == "binance"
    assert sink.data_quality == []


def test_reconciled_disagreement_halts() -> None:
    a = _FakeFeed("binance", frame=_frame(_T0, close=100.0, source="ccxt:binance"))
    b = _FakeFeed("kraken", frame=_frame(_T0, close=105.0, source="ccxt:kraken"))
    sink = CollectingSink()
    router = _router(_registry(a, b), sink)
    with pytest.raises(ReconciliationError, match="disagree"):
        router.get_bars_reconciled(CRYPTO_PRICES, "BTC/USDT", "1h", tolerance=0.005)
    assert len(sink.data_quality) == 1
    assert sink.data_quality[0].action == "halt"
    assert sink.data_quality[0].symbol == "BTC/USDT"


def test_reconciled_skips_failing_source() -> None:
    # One source errors during reconciliation; the other still serves and a
    # single-value reconcile passes (nothing to disagree with).
    bad = _FakeFeed("binance", error=ConnectionError("down"))
    good = _FakeFeed("kraken", frame=_frame(_T0, close=100.0, source="ccxt:kraken"))
    sink = CollectingSink()
    result = _router(_registry(bad, good), sink).get_bars_reconciled(
        CRYPTO_PRICES, "BTC/USDT", "1h", tolerance=0.005
    )
    assert result.source == "kraken"
    assert sink.data_quality == []


def test_reconciled_all_fail_raises() -> None:
    a = _FakeFeed("binance", error=ConnectionError("a"))
    b = _FakeFeed("kraken", error=ConnectionError("b"))
    sink = CollectingSink()
    with pytest.raises(NoHealthySourceError):
        _router(_registry(a, b), sink).get_bars_reconciled(
            CRYPTO_PRICES, "BTC/USDT", "1h", tolerance=0.005
        )
