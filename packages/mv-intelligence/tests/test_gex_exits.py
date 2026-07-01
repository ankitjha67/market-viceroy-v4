"""Tests for the Vol Desk exit framework (mv.intelligence.gex.exits)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from mv.intelligence.gex.exits import Position, evaluate_exit
from mv.intelligence.gex.types import GammaRow

_POS = Position(symbol="T", entry=Decimal("100"), entry_day=0, t1=Decimal("110"))


def _row(spot: str, **over: Any) -> GammaRow:
    base: dict[str, Any] = {
        "symbol": "T",
        "spot": Decimal(spot),
        "dealer_delta": Decimal("0.8"),
        "prior_delta": Decimal("0.2"),
        "grade": 10,
        "minervini": 95,
        "p_trans": Decimal("99"),
        "n_trans": Decimal("95"),
        "zero_gex": Decimal("97"),
        "plus_gex": Decimal("110"),
        "cotmp": Decimal("94"),
        "cotmc": Decimal("112"),
    }
    base.update(over)
    return GammaRow(**base)


def test_stop1_close_below_ntrans_exits() -> None:
    d = evaluate_exit(_POS, _row("94"), day=1)  # below nTrans 95
    assert d.action == "EXIT" and "nTrans" in d.reason


def test_stop2_hard_10pct_below_ptrans_exits() -> None:
    d = evaluate_exit(
        _POS, _row("90", n_trans=Decimal("80")), day=1
    )  # -10%, below pTrans, above nTrans
    assert d.action == "EXIT" and "-10%" in d.reason


def test_t1_locks_by_default() -> None:
    d = evaluate_exit(_POS, _row("110"), day=1)  # spot == t1
    assert d.action == "LOCK_T1"


def test_t1_takes_when_requested() -> None:
    d = evaluate_exit(_POS, _row("111"), day=1, take_profit_at_t1=True)
    assert d.action == "TAKE_T1"


def test_stop3_time_stop_without_progress() -> None:
    # Day 7, spot 101 -> only 10% of the way to T1 (< 50%).
    d = evaluate_exit(_POS, _row("101"), day=7)
    assert d.action == "EXIT" and "stop 3" in d.reason


def test_stop4_stalling_three_flat_sessions() -> None:
    d = evaluate_exit(
        _POS,
        _row("102"),
        day=3,
        daily_progress=[Decimal("0.05"), Decimal("0.02"), Decimal("0.03")],
    )
    assert d.action == "EXIT" and "stalling" in d.reason


def test_holds_above_ptrans() -> None:
    d = evaluate_exit(_POS, _row("104"), day=2, daily_progress=[Decimal("0.4")])
    assert d.action == "HOLD"


def test_watch_below_ptrans_above_ntrans() -> None:
    d = evaluate_exit(
        _POS, _row("98", n_trans=Decimal("95")), day=2
    )  # below pTrans 99, above nTrans
    assert d.action == "WATCH"
