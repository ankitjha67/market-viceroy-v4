"""Tests for market-regime detection and the regime-weighted ensemble."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from mv.agents.baseline.pipeline import StrategySignal, ensemble_decision
from mv.agents.baseline.regime import (
    detect_regime,
    efficiency_ratio,
    family_weight,
)

_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_efficiency_ratio_straight_trend_is_one() -> None:
    # A monotonic move: path length == net move -> ER == 1.
    assert efficiency_ratio([1.0, 2.0, 3.0, 4.0, 5.0], lookback=10) == 1.0


def test_efficiency_ratio_round_trip_is_zero() -> None:
    # Ends where it started: net move 0 -> ER 0 (pure chop).
    assert efficiency_ratio([1.0, 2.0, 1.0, 2.0, 1.0], lookback=10) == 0.0


def test_efficiency_ratio_partial_chop() -> None:
    # net |3-1| = 2 over path 1+1+1+1 = 4 -> 0.5.
    assert efficiency_ratio([1.0, 2.0, 3.0, 2.0, 3.0], lookback=10) == 0.5


def test_detect_regime_trending_upweights_trend() -> None:
    closes = [float(i) for i in range(1, 60)]  # straight up -> ER 1
    r = detect_regime(closes, lookback=30, floor=0.1)
    assert r.label == "trending"
    assert r.trend_score == 1.0
    assert r.trend_weight > r.meanrev_weight
    assert abs(r.trend_weight + r.meanrev_weight - 1.0) < 1e-9  # weights sum to 1
    assert r.trend_weight == 0.9 and r.meanrev_weight == 0.1  # floor 0.1 honored


def test_detect_regime_ranging_upweights_meanrev() -> None:
    closes = [1.0, 2.0] * 30  # zig-zag -> ER 0
    r = detect_regime(closes, lookback=30, floor=0.1)
    assert r.label == "ranging"
    assert r.meanrev_weight > r.trend_weight
    assert r.meanrev_weight == 0.9 and r.trend_weight == 0.1


def test_detect_regime_floor_is_clamped() -> None:
    # An absurd floor can't invert the weighting; it is clamped below 0.5.
    r = detect_regime([float(i) for i in range(1, 40)], lookback=30, floor=0.9)
    assert 0.0 <= r.meanrev_weight <= r.trend_weight <= 1.0


def test_family_weight_routes_by_category() -> None:
    r = detect_regime([float(i) for i in range(1, 40)], lookback=30)
    assert family_weight("trend", r) == r.trend_weight
    assert family_weight("meanrev", r) == r.meanrev_weight
    assert family_weight("unknown", r) == r.trend_weight  # default to trend


def _sig(name: str, weight: str) -> StrategySignal:
    return StrategySignal(strategy=name, weight=Decimal(weight))


def test_weighted_ensemble_favours_the_upweighted_family() -> None:
    # One long trend vote, one short meanrev vote. Equal weight -> net 0 (HOLD).
    signals = [_sig("trend_a", "1"), _sig("mr_a", "-1")]
    flat = ensemble_decision(signals, instrument="BTC/USDT", ts=_TS, snapshot_id="s")
    assert flat.action == "HOLD"
    # Upweight the trend family -> the BUY wins.
    weighted = ensemble_decision(
        signals,
        instrument="BTC/USDT",
        ts=_TS,
        snapshot_id="s",
        weights={"trend_a": Decimal("0.9"), "mr_a": Decimal("0.1")},
        note="regime trending",
    )
    assert weighted.action == "BUY"
    assert "regime trending" in weighted.rationale


def test_weighted_ensemble_zero_weights_fall_back_to_equal() -> None:
    signals = [_sig("a", "1"), _sig("b", "1")]
    out = ensemble_decision(
        signals,
        instrument="BTC/USDT",
        ts=_TS,
        snapshot_id="s",
        weights={"a": Decimal("0"), "b": Decimal("0")},
    )
    assert out.action == "BUY"  # degenerate all-zero weights -> equal weight, not a crash
