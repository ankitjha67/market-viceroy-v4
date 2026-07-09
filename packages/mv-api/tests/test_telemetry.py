"""Tests for the serve realism helpers: source telemetry + capital resolution."""

from __future__ import annotations

from decimal import Decimal

import pytest
from mv.api.cli import resolve_start_equity
from mv.api.telemetry import SourceTelemetry, budget_for, health_status, percentile


def test_percentile_interpolates_and_handles_edges() -> None:
    assert percentile([], 0.5) == 0.0
    assert percentile([42.0], 0.9) == 42.0
    assert percentile([10.0, 20.0, 30.0, 40.0], 0.5) == 25.0  # midpoint interp
    assert percentile([10.0, 20.0, 30.0, 40.0], 1.0) == 40.0


def test_budget_defaults_for_unknown_source() -> None:
    assert budget_for("ccxt:binance") == 1200
    assert budget_for("ccxt:something-new") == 60  # cautious default


def test_health_status_thresholds() -> None:
    assert health_status(0, 0, samples=0) == "amber"  # no reading yet
    assert health_status(100, 10, samples=5) == "green"
    assert health_status(1200, 10, samples=5) == "amber"  # slow p95
    assert health_status(100, 80, samples=5) == "amber"  # quota pressure
    assert health_status(2500, 10, samples=5) == "red"  # very slow
    assert health_status(100, 95, samples=5) == "red"  # quota exhausted


def test_telemetry_reports_measured_latency_not_zero() -> None:
    tel = SourceTelemetry()
    for i, lat in enumerate([40.0, 50.0, 60.0, 300.0]):
        tel.record("ccxt:kraken", lat, at=100.0 + i)  # kraken: a 60/min budget
    view = tel.view("ccxt:kraken", at=104.0)
    assert view["samples"] == 4
    assert view["latency_p50_ms"] == 55  # real measured median, never 0
    assert view["latency_p95_ms"] >= 60
    assert view["quota_burn_pct"] == 7  # round(100 * 4 / 60) — a real utilisation
    assert view["status"] in {"green", "amber", "red"}


def test_telemetry_quota_only_counts_the_recent_window() -> None:
    tel = SourceTelemetry()
    tel.record("ccxt:kraken", 30.0, at=0.0)  # old, outside the 60s window
    for i in range(30):
        tel.record("ccxt:kraken", 30.0, at=1000.0 + i)  # 30 recent, budget 60/min
    view = tel.view("ccxt:kraken", at=1030.0)
    # 30 recent requests / 60 budget -> ~50%; the stale one at t=0 is excluded.
    assert 45 <= view["quota_burn_pct"] <= 55


def test_resolve_start_equity_precedence_and_default() -> None:
    assert resolve_start_equity(None, None) == Decimal("5000")
    assert resolve_start_equity(None, "25000") == Decimal("25000")  # env
    assert resolve_start_equity("100000", "25000") == Decimal("100000")  # cli wins


def test_resolve_start_equity_rejects_bad_input() -> None:
    with pytest.raises(SystemExit):
        resolve_start_equity("not-a-number", None)
    with pytest.raises(SystemExit):
        resolve_start_equity("0", None)
    with pytest.raises(SystemExit):
        resolve_start_equity("-500", None)
