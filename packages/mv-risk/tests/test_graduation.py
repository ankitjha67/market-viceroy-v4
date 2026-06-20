"""Unit tests for the graduation gate (BR-005, US-010, FR-P6)."""

from __future__ import annotations

from decimal import Decimal

from mv.risk.graduation import (
    GraduationThresholds,
    PaperRecord,
    evaluate_graduation,
)


def _record(**over: object) -> PaperRecord:
    base = {
        "strategy": "ema_cross_12_26",
        "gate_status": "active",
        "months_paper": 4.0,
        "oos_sharpe": 1.3,
        "max_drawdown": Decimal("0.08"),
        "n_trades": 140,
        "projection_honesty": None,
    }
    base.update(over)
    return PaperRecord(**base)  # type: ignore[arg-type]


def test_clean_record_is_eligible_with_cap() -> None:
    verdict = evaluate_graduation(_record())
    assert verdict.eligible is True
    assert verdict.reasons == []
    assert verdict.live_cap_pct == Decimal("0.01")  # conservative 1% cap


def test_synthetic_or_observe_never_eligible() -> None:
    verdict = evaluate_graduation(_record(gate_status="observe"))
    assert verdict.eligible is False
    assert any("not 'active'" in r for r in verdict.reasons)
    assert verdict.live_cap_pct == Decimal("0")


def test_short_paper_record_blocks() -> None:
    verdict = evaluate_graduation(_record(months_paper=2.0))
    assert verdict.eligible is False
    assert any("mo <" in r for r in verdict.reasons)


def test_weak_sharpe_blocks() -> None:
    assert evaluate_graduation(_record(oos_sharpe=0.8)).eligible is False


def test_deep_drawdown_blocks() -> None:
    verdict = evaluate_graduation(_record(max_drawdown=Decimal("0.15")))
    assert verdict.eligible is False
    assert any("drawdown" in r for r in verdict.reasons)


def test_too_few_trades_blocks() -> None:
    assert evaluate_graduation(_record(n_trades=40)).eligible is False


def test_projection_honesty_only_checked_when_present() -> None:
    # No live history yet -> the honesty check cannot fail.
    assert evaluate_graduation(_record(projection_honesty=None)).eligible is True
    # A live gap within tolerance stays eligible.
    assert evaluate_graduation(_record(projection_honesty=0.3)).eligible is True
    # A live gap beyond tolerance blocks (ongoing honesty breach).
    breached = evaluate_graduation(_record(projection_honesty=0.9))
    assert breached.eligible is False
    assert any("projection gap" in r for r in breached.reasons)


def test_all_shortfalls_reported_together() -> None:
    verdict = evaluate_graduation(
        _record(gate_status="failed", months_paper=1.0, oos_sharpe=0.1, n_trades=5)
    )
    assert verdict.eligible is False
    assert len(verdict.reasons) >= 4


def test_aggressive_bar_is_looser() -> None:
    record = _record(months_paper=1.5, oos_sharpe=0.6, n_trades=35, max_drawdown=Decimal("0.18"))
    assert evaluate_graduation(record, GraduationThresholds.conservative()).eligible is False
    assert evaluate_graduation(record, GraduationThresholds.aggressive()).eligible is True
