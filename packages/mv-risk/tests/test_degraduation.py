"""Unit tests for de-graduation (revert to paper; governed, de-risk only)."""

from __future__ import annotations

from decimal import Decimal

from mv.risk.degraduation import LiveRecord, evaluate_degradation


def _record(**over: object) -> LiveRecord:
    base = {
        "strategy": "ema_cross",
        "projection_gap": 0.2,
        "live_max_drawdown": Decimal("0.05"),
        "breached_limits": 0,
    }
    base.update(over)
    return LiveRecord(**base)  # type: ignore[arg-type]


def test_healthy_live_record_is_not_degraded() -> None:
    verdict = evaluate_degradation(_record())
    assert verdict.should_degrade is False
    assert verdict.reasons == []


def test_projection_gap_breach_degrades() -> None:
    verdict = evaluate_degradation(_record(projection_gap=0.9))
    assert verdict.should_degrade is True
    assert any("projection gap" in r for r in verdict.reasons)


def test_drawdown_breach_degrades() -> None:
    verdict = evaluate_degradation(_record(live_max_drawdown=Decimal("0.18")))
    assert verdict.should_degrade is True
    assert any("drawdown" in r for r in verdict.reasons)


def test_limit_breach_degrades() -> None:
    verdict = evaluate_degradation(_record(breached_limits=2))
    assert verdict.should_degrade is True
    assert any("limit breach" in r for r in verdict.reasons)


def test_unmeasured_projection_gap_does_not_degrade_alone() -> None:
    verdict = evaluate_degradation(_record(projection_gap=None))
    assert verdict.should_degrade is False
