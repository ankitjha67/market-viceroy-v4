"""Mistake taxonomy (PRD FR-P2) — auto-classify losers by cause + track cost.

Given a trade's causal attribution (and a little context), assign one mistake
category from the taxonomy and the cost it carried. The rule is: **context
signals first** (a data-quality event, a correlated pile-up, an exit the market
then reversed), then the **dominant adverse component** of the decomposition
(the single biggest loss contributor). Only losses are classified; a profitable
trade returns ``None``. :func:`mistake_stats` rolls the tags up into per-category
frequency + cumulative cost over time. Pure and deterministic; thresholds are
module constants, documented and tunable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from mv.postmortem.attribution import TradeAttribution

# Categories (PRD FR-P2).
FALSE_SIGNAL = "false_signal"
LATE_ENTRY = "late_entry"
OVERSIZING = "oversizing"
STOP_TOO_TIGHT = "stop_too_tight"
REGIME_MISREAD = "regime_misread"
STALE_DATA = "stale_data"
SLIPPAGE_BLOWOUT = "slippage_blowout"
CORRELATED_PILEUP = "correlated_pileup"

# A correlated cluster of this many concurrent positions counts as a pile-up.
_PILEUP_THRESHOLD = 2

# The component → category map for the dominant-adverse-component fallback.
_COMPONENT_CATEGORY: dict[str, str] = {
    "signal": FALSE_SIGNAL,
    "timing": LATE_ENTRY,
    "sizing": OVERSIZING,
    "slippage": SLIPPAGE_BLOWOUT,
    "regime": REGIME_MISREAD,
}


@dataclass(frozen=True, slots=True)
class MistakeContext:
    """Extra signals the attribution alone does not carry."""

    had_data_quality_event: bool = False
    """A data-quality/reconciliation event fired during the trade window."""

    concurrent_correlated: int = 0
    """Count of concurrent positions in the same correlated cluster."""

    recovered_after_exit: bool = False
    """Price reversed in the trade's favour shortly after we exited at a loss."""


@dataclass(frozen=True, slots=True)
class Mistake:
    """One classified mistake: which trade, which category, what it cost."""

    trade_id: str
    category: str
    cost: Decimal  # positive magnitude of the adverse contribution
    detail: str = ""


def _adverse_components(attr: TradeAttribution) -> dict[str, Decimal]:
    raw = {
        "signal": attr.signal,
        "timing": attr.timing,
        "sizing": attr.sizing,
        "slippage": attr.slippage,
        "regime": attr.regime,
    }
    return {name: value for name, value in raw.items() if value is not None and value < 0}


def classify(attr: TradeAttribution, context: MistakeContext | None = None) -> Mistake | None:
    """Classify a losing trade into one mistake category, or ``None`` if it won.

    Returns ``None`` for a non-loss (``net_pnl >= 0``) or an undecomposed
    attribution. Context signals take precedence over the component fallback.
    """
    ctx = context or MistakeContext()
    if attr.net_pnl >= 0 or not attr.is_decomposed():
        return None

    loss = -attr.net_pnl  # positive magnitude of the loss

    # Context signals first.
    if ctx.had_data_quality_event:
        return Mistake(attr.trade_id, STALE_DATA, loss, "data-quality event during the trade")
    if ctx.concurrent_correlated >= _PILEUP_THRESHOLD:
        return Mistake(
            attr.trade_id,
            CORRELATED_PILEUP,
            loss,
            f"{ctx.concurrent_correlated} concurrent correlated positions",
        )
    if ctx.recovered_after_exit:
        return Mistake(attr.trade_id, STOP_TOO_TIGHT, loss, "price reversed in favour after exit")

    # Otherwise, blame the single biggest adverse component.
    adverse = _adverse_components(attr)
    if not adverse:
        return Mistake(attr.trade_id, FALSE_SIGNAL, loss, "loss with no single adverse component")
    component = min(adverse, key=lambda name: adverse[name])
    category = _COMPONENT_CATEGORY[component]
    cost = -adverse[component]
    return Mistake(attr.trade_id, category, cost, f"dominant adverse component: {component}")


@dataclass
class CategoryStat:
    """Per-category rollup: how often, and how much it has cost cumulatively."""

    count: int = 0
    cost: Decimal = field(default_factory=lambda: Decimal("0"))


def mistake_stats(mistakes: list[Mistake]) -> dict[str, CategoryStat]:
    """Aggregate mistakes into per-category frequency + cumulative cost."""
    stats: dict[str, CategoryStat] = {}
    for mistake in mistakes:
        stat = stats.setdefault(mistake.category, CategoryStat())
        stat.count += 1
        stat.cost += mistake.cost
    return stats


__all__ = [
    "CORRELATED_PILEUP",
    "FALSE_SIGNAL",
    "LATE_ENTRY",
    "OVERSIZING",
    "REGIME_MISREAD",
    "SLIPPAGE_BLOWOUT",
    "STALE_DATA",
    "STOP_TOO_TIGHT",
    "CategoryStat",
    "Mistake",
    "MistakeContext",
    "classify",
    "mistake_stats",
]
