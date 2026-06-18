"""Unit tests for the improvement ledger (FR-P4)."""

from __future__ import annotations

from mv.postmortem.improvement import ImprovementEntry, ImprovementLedger


def test_entry_improved_flag() -> None:
    up = ImprovementEntry(
        "strategy_weight", "raise ema weight", before_metric=0.8, after_metric=1.1
    )
    down = ImprovementEntry(
        "strategy_weight", "raise ema weight", before_metric=1.1, after_metric=0.8
    )
    unknown = ImprovementEntry("param_prior", "widen prior")
    assert up.improved is True
    assert down.improved is False
    assert unknown.improved is False


def test_ledger_records_and_filters() -> None:
    ledger = ImprovementLedger()
    ledger.record(
        ImprovementEntry(
            "strategy_weight", "cut rsi weight", mistake_category="false_signal", adopted=True
        )
    )
    ledger.record(ImprovementEntry("risk_limit", "tighten stop", mistake_category="stop_too_tight"))
    assert len(ledger.entries) == 2
    assert len(ledger.adopted()) == 1
    assert ledger.for_category("false_signal")[0].change_kind == "strategy_weight"
