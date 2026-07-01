"""Tests for the Vol Desk regime gate (mv.intelligence.gex.regime)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from mv.intelligence.gex.regime import (
    TRACK_B_CONTINUATION_MIN_GATES,
    TRACK_P2P_MIN_GATES,
    RegimeSnapshot,
    regime_gate,
)


def _snap(**over: Any) -> RegimeSnapshot:
    base: dict[str, Any] = {
        "basket_change": Decimal("0.01"),  # +1%
        "bull_bear_ratio": Decimal("4.0"),  # 4:1
        "vix_dealer_delta": Decimal("-0.5"),  # bearish vol -> bullish equities
    }
    base.update(over)
    return RegimeSnapshot(**base)


def test_all_three_gates_pass() -> None:
    gate = regime_gate(_snap())
    assert gate.passed == 3
    assert gate.allows(need=TRACK_B_CONTINUATION_MIN_GATES)


def test_flat_basket_drops_to_two_of_three() -> None:
    gate = regime_gate(_snap(basket_change=Decimal("0.002")))  # +0.2% < 0.5%
    assert not gate.basket_ok
    assert gate.passed == 2
    assert gate.allows(need=TRACK_P2P_MIN_GATES)  # P2P may run at 2/3
    assert not gate.allows(need=TRACK_B_CONTINUATION_MIN_GATES)  # B-Continuation needs 3/3


def test_positive_vix_positioning_fails_vix_gate() -> None:
    assert not regime_gate(_snap(vix_dealer_delta=Decimal("0.2"))).vix_ok


def test_weak_breadth_fails_the_breadth_gate() -> None:
    assert not regime_gate(_snap(bull_bear_ratio=Decimal("2.5"))).breadth_ok


def test_hyg_divergence_flag_carried_through() -> None:
    assert regime_gate(_snap(hyg_bearish=True)).hyg_bearish
