"""Unit tests for staleness, reconciliation, health, registry, and ladders."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from mv.failover.errors import StalenessError
from mv.failover.health import HealthStatus, HealthTracker
from mv.failover.ladders import build_default_registry, crypto_prices_ladder
from mv.failover.reconcile import reconcile_prices
from mv.failover.registry import CRYPTO_PRICES, DomainKey, LadderRegistry
from mv.failover.staleness import (
    guard_staleness,
    is_stale,
    max_staleness_seconds,
    timeframe_seconds,
)

_T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


# --- staleness ------------------------------------------------------------


def test_timeframe_seconds_and_max() -> None:
    assert timeframe_seconds("1h") == 3600
    assert max_staleness_seconds("1h", multiple=2.0) == 7200.0


def test_unknown_timeframe_raises() -> None:
    with pytest.raises(ValueError, match="unknown timeframe"):
        timeframe_seconds("7s")


def test_is_stale() -> None:
    assert is_stale(_T0, _T0 + timedelta(hours=3), "1h") is True
    assert is_stale(_T0, _T0 + timedelta(minutes=30), "1h") is False


def test_guard_staleness_raises() -> None:
    with pytest.raises(StalenessError, match="old"):
        guard_staleness(_T0, _T0 + timedelta(hours=5), "1h", source="ccxt:binance")
    # Fresh: no raise.
    guard_staleness(_T0, _T0 + timedelta(minutes=10), "1h", source="ccxt:binance")


# --- reconciliation -------------------------------------------------------


def test_reconcile_single_source_ok() -> None:
    result = reconcile_prices({"a": 100.0}, tolerance=0.001)
    assert result.ok is True
    assert result.discrepancy == 0.0


def test_reconcile_agreement() -> None:
    result = reconcile_prices({"a": 100.0, "b": 100.2}, tolerance=0.005)
    assert result.ok is True


def test_reconcile_disagreement() -> None:
    result = reconcile_prices({"a": 100.0, "b": 101.0}, tolerance=0.005)
    assert result.ok is False
    assert result.discrepancy > 0.005


def test_reconcile_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError):
        reconcile_prices({"a": 1.0, "b": 2.0}, tolerance=-1)
    with pytest.raises(ValueError, match="zero mean"):
        reconcile_prices({"a": 1.0, "b": -1.0}, tolerance=0.1)


# --- health ---------------------------------------------------------------


def test_health_green_amber_red() -> None:
    tracker = HealthTracker()
    for _ in range(10):
        tracker.record_success("green", 5.0)
    assert tracker.snapshot("green").status is HealthStatus.GREEN

    for _ in range(9):
        tracker.record_success("amber", 5.0)
    tracker.record_failure("amber")
    assert tracker.snapshot("amber").status is HealthStatus.AMBER

    tracker.record_success("red", 5.0)
    tracker.record_failure("red")
    assert tracker.snapshot("red").status is HealthStatus.RED


def test_health_latency_percentiles() -> None:
    tracker = HealthTracker()
    for latency in (10.0, 20.0, 30.0, 40.0):
        tracker.record_success("s", latency)
    snap = tracker.snapshot("s")
    assert snap.p50_latency_ms == 20.0
    assert snap.p95_latency_ms == 40.0
    assert snap.total == 4
    assert set(tracker.all()) == {"s"}


# --- registry + ladders ---------------------------------------------------


def test_registry_orders_by_priority() -> None:
    registry = build_default_registry()
    ladder = registry.ladder(CRYPTO_PRICES)
    assert [s.name for s in ladder] == ["ccxt:binance", "ccxt:kraken", "ccxt:coinbase"]
    assert [s.priority for s in ladder] == [0, 1, 2]


def test_crypto_ladder_feed_names() -> None:
    specs = crypto_prices_ladder()
    assert specs[0].feed.name == "ccxt:binance"
    assert specs[0].licensing_tag == "internal-only"


def test_registry_rejects_empty_and_duplicates() -> None:
    registry = LadderRegistry()
    with pytest.raises(ValueError, match="at least one source"):
        registry.register(CRYPTO_PRICES, [])
    specs = crypto_prices_ladder()
    dup = [specs[0], specs[0]]
    with pytest.raises(ValueError, match="duplicate source names"):
        registry.register(CRYPTO_PRICES, dup)


def test_registry_unknown_domain_raises() -> None:
    registry = LadderRegistry()
    with pytest.raises(KeyError):
        registry.ladder(DomainKey("crypto", "global", "prices", "realtime"))


def test_domain_str() -> None:
    assert str(CRYPTO_PRICES) == "crypto.prices"
