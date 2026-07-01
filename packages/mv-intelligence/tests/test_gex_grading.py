"""Tests for Vol Desk setup grading (mv.intelligence.gex.grading)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from mv.intelligence.gex.grading import grade_setup
from mv.intelligence.gex.mock_feed import mock_gamma_screen
from mv.intelligence.gex.types import GammaRow


def _row(**over: Any) -> GammaRow:
    base: dict[str, Any] = {
        "symbol": "T",
        "spot": Decimal("100"),
        "dealer_delta": Decimal("0.8"),
        "prior_delta": Decimal("0.2"),  # db_change 0.60
        "grade": 10,
        "minervini": 95,
        "p_trans": Decimal("99"),
        "n_trans": Decimal("95"),
        "zero_gex": Decimal("97"),
        "plus_gex": Decimal("108"),  # R/R = 8
        "cotmp": Decimal("94"),  # 6% cushion
        "cotmc": Decimal("112"),
    }
    base.update(over)
    return GammaRow(**base)


def test_clean_setup_confirms_with_the_close() -> None:
    assert grade_setup(_row(), confirmed_close_above_ptrans=True).status == "CONFIRMED"


def test_clean_setup_is_pending_without_the_close() -> None:
    # Spot above pTrans but no confirmed 5-min close yet -> watching.
    assert grade_setup(_row()).status == "PENDING"


def test_grade_below_nine_hard_blocks() -> None:
    v = grade_setup(_row(grade=8), confirmed_close_above_ptrans=True)
    assert v.status == "BLOCKED"
    assert any("grade 8" in r for r in v.reasons)


def test_spike_crash_hard_blocks() -> None:
    v = grade_setup(_row(spike_crash=True), confirmed_close_above_ptrans=True)
    assert v.status == "BLOCKED"
    assert any("spike-crash" in r for r in v.reasons)


def test_db_change_below_threshold_blocks() -> None:
    v = grade_setup(_row(prior_delta=Decimal("0.4")), confirmed_close_above_ptrans=True)  # db 0.4
    assert v.status == "BLOCKED"
    assert any("db_change" in r for r in v.reasons)


def test_deep_gets_the_lower_db_bar() -> None:
    # Grade 11, db_change 0.35 -> clears the DEEP 0.30 bar (would fail the 0.50 bar).
    v = grade_setup(
        _row(grade=11, dealer_delta=Decimal("0.95"), prior_delta=Decimal("0.60")),
        confirmed_close_above_ptrans=True,
    )
    assert v.status == "CONFIRMED"


def test_pegged_delta_is_exempt_from_db() -> None:
    v = grade_setup(
        _row(dealer_delta=Decimal("1.0"), prior_delta=Decimal("1.0"), delta_pegged_2s=True),
        confirmed_close_above_ptrans=True,
    )
    assert v.status == "CONFIRMED"
    assert any("sustained" in r for r in v.reasons)


def test_thin_cushion_blocks_at_the_two_percent_bar() -> None:
    # db_change 0.60 (< the 0.70 "high" bar) so the 2% cushion applies; 1.5% fails.
    v = grade_setup(_row(cotmp=Decimal("98.5")), confirmed_close_above_ptrans=True)
    assert v.status == "BLOCKED"
    assert any("cushion" in r for r in v.reasons)


def test_reward_risk_below_two_blocks() -> None:
    # plus_gex 100.5 -> upside 0.5 over downside 1.0 -> R/R 0.5 < 2.
    v = grade_setup(_row(plus_gex=Decimal("100.5")), confirmed_close_above_ptrans=True)
    assert v.status == "BLOCKED"
    assert any("R/R" in r for r in v.reasons)


def test_mock_screen_grades_span_the_cases() -> None:
    by_symbol = {
        r.symbol: grade_setup(r, confirmed_close_above_ptrans=True).status
        for r in mock_gamma_screen()
    }
    assert by_symbol["AAPL"] == "CONFIRMED"
    assert by_symbol["WEAK"] == "BLOCKED"  # grade 8
    assert by_symbol["SPK"] == "BLOCKED"  # spike-crash
    assert by_symbol["DEEP"] == "CONFIRMED"  # DEEP relaxations
