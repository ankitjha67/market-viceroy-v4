"""Unit tests for the deterministic ensemble decision pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from mv.agents.baseline.pipeline import StrategySignal, ensemble_decision
from mv.agents.schemas import TradeDecision

_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _decide(weights: list[tuple[str, str]]) -> TradeDecision:
    signals = [StrategySignal(name, Decimal(w)) for name, w in weights]
    return ensemble_decision(signals, instrument="BTC/USDT", ts=_TS, snapshot_id="snap-1")


def test_all_long_is_buy_full_conviction() -> None:
    d = _decide([("ema", "1"), ("sma", "1"), ("donchian", "1")])
    assert d.action == "BUY"
    assert d.target_size == Decimal("1")
    assert d.conviction == 1.0
    assert d.dissent == "none"


def test_all_short_is_sell() -> None:
    d = _decide([("ema", "-1"), ("sma", "-1")])
    assert d.action == "SELL"
    assert d.target_size == Decimal("-1")
    assert d.conviction == 1.0


def test_balanced_is_hold() -> None:
    d = _decide([("ema", "1"), ("sma", "-1")])
    assert d.action == "HOLD"
    assert d.target_size == Decimal("0")


def test_below_threshold_is_hold() -> None:
    # ensemble = 0.04 < 0.05 threshold.
    d = _decide([("ema", "0.04"), ("sma", "0.04")])
    assert d.action == "HOLD"


def test_majority_long_buy_with_partial_conviction_and_dissent() -> None:
    # 3 long (+1), 1 short (-0.8): ensemble = (3 - 0.8)/4 = 0.55 -> BUY.
    d = _decide([("a", "1"), ("b", "1"), ("c", "1"), ("bear", "-0.8")])
    assert d.action == "BUY"
    assert d.conviction == 0.75  # 3 of 4 long
    assert "bear" in d.dissent  # strongest opposing strategy


def test_dissent_none_when_unanimous_direction() -> None:
    d = _decide([("a", "0.5"), ("b", "0.7")])
    assert d.action == "BUY"
    assert d.dissent == "none"


def test_hold_dissent_flags_directional_outlier() -> None:
    # Balanced -> HOLD, but one strategy is strongly directional.
    d = _decide([("a", "0.9"), ("b", "-0.9")])
    assert d.action == "HOLD"
    assert d.dissent != "none"


def test_empty_signals_raise() -> None:
    with pytest.raises(ValueError, match="at least one"):
        ensemble_decision([], instrument="BTC/USDT", ts=_TS, snapshot_id="s")


def test_rationale_summarizes_votes() -> None:
    d = _decide([("a", "1"), ("b", "1"), ("c", "-1")])
    assert "2 long" in d.rationale
    assert "1 short" in d.rationale
    assert "BUY" in d.rationale
