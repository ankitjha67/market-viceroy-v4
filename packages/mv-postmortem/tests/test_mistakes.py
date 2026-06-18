"""Unit tests for the mistake taxonomy (FR-P2)."""

from __future__ import annotations

from decimal import Decimal

from mv.postmortem.attribution import TradeAttribution
from mv.postmortem.mistakes import (
    CORRELATED_PILEUP,
    FALSE_SIGNAL,
    LATE_ENTRY,
    REGIME_MISREAD,
    SLIPPAGE_BLOWOUT,
    STALE_DATA,
    STOP_TOO_TIGHT,
    MistakeContext,
    classify,
    mistake_stats,
)


def _attr(net: str, **components: str) -> TradeAttribution:
    base = {
        "signal": "0",
        "timing": "0",
        "sizing": "0",
        "slippage": "0",
        "fees": "0",
        "regime": "0",
    }
    base.update(components)
    return TradeAttribution(
        trade_id="t1",
        net_pnl=Decimal(net),
        **{k: Decimal(v) for k, v in base.items()},
    )


def test_winning_trade_is_not_a_mistake() -> None:
    assert classify(_attr("50", signal="50")) is None


def test_undecomposed_attribution_returns_none() -> None:
    assert classify(TradeAttribution(trade_id="t", net_pnl=Decimal("-10"))) is None


def test_false_signal_when_signal_dominates_loss() -> None:
    m = classify(_attr("-30", signal="-30"))
    assert m is not None and m.category == FALSE_SIGNAL
    assert m.cost == Decimal("30")


def test_late_entry_when_timing_dominates() -> None:
    m = classify(_attr("-20", signal="-5", timing="-15"))
    assert m is not None and m.category == LATE_ENTRY


def test_slippage_blowout_when_slippage_dominates() -> None:
    m = classify(_attr("-12", slippage="-12"))
    assert m is not None and m.category == SLIPPAGE_BLOWOUT


def test_regime_misread_when_regime_dominates() -> None:
    m = classify(_attr("-18", regime="-18"))
    assert m is not None and m.category == REGIME_MISREAD


def test_stale_data_context_takes_precedence() -> None:
    m = classify(_attr("-10", signal="-10"), MistakeContext(had_data_quality_event=True))
    assert m is not None and m.category == STALE_DATA


def test_correlated_pileup_context() -> None:
    m = classify(_attr("-10", signal="-10"), MistakeContext(concurrent_correlated=3))
    assert m is not None and m.category == CORRELATED_PILEUP


def test_stop_too_tight_context() -> None:
    m = classify(_attr("-10", signal="-10"), MistakeContext(recovered_after_exit=True))
    assert m is not None and m.category == STOP_TOO_TIGHT


def test_mistake_stats_aggregates_frequency_and_cost() -> None:
    mistakes = [
        m
        for m in (
            classify(_attr("-30", signal="-30")),
            classify(_attr("-10", signal="-10")),
            classify(_attr("-12", slippage="-12")),
        )
        if m is not None
    ]
    stats = mistake_stats(mistakes)
    assert stats[FALSE_SIGNAL].count == 2
    assert stats[FALSE_SIGNAL].cost == Decimal("40")
    assert stats[SLIPPAGE_BLOWOUT].count == 1
