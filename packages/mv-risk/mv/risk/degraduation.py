"""De-graduation (PRD §13 follow-on) — pull a strategy back to paper, governed.

The mirror of graduation: a live strategy is **reverted to paper** when its live
record breaks the honest-projection contract (|live − paper Sharpe| beyond
tolerance), draws down past the limit, or trips a risk limit. De-graduation only
ever **de-risks** — it never grants more capital or scope — and is journaled by
the caller. Reuses the :class:`~mv.risk.graduation.GraduationThresholds` bar so
the de-grad tolerances match the grad tolerances. Pure and unit-tested.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from mv.risk.graduation import GraduationThresholds


@dataclass(frozen=True, slots=True)
class LiveRecord:
    """A graduated strategy's live record, the input to the de-grad check."""

    strategy: str
    projection_gap: float | None  # |live − paper Sharpe|; None if not yet measured
    live_max_drawdown: Decimal  # positive fraction of peak equity
    breached_limits: int = 0  # count of risk-limit breaches in the window


@dataclass(frozen=True, slots=True)
class DegradationVerdict:
    """Whether to revert the strategy to paper, and why."""

    should_degrade: bool
    reasons: list[str] = field(default_factory=list)


def evaluate_degradation(
    record: LiveRecord, thresholds: GraduationThresholds | None = None
) -> DegradationVerdict:
    """Decide whether ``record`` must be de-graduated (reverted to paper)."""
    bar = thresholds or GraduationThresholds.conservative()
    reasons: list[str] = []

    if record.projection_gap is not None and record.projection_gap > bar.max_projection_gap:
        reasons.append(
            f"projection gap {record.projection_gap:.2f} > {bar.max_projection_gap:.2f} "
            "(live is not tracking paper)"
        )
    if record.live_max_drawdown > bar.max_drawdown:
        reasons.append(f"live drawdown {record.live_max_drawdown} > {bar.max_drawdown}")
    if record.breached_limits > 0:
        reasons.append(f"{record.breached_limits} risk-limit breach(es) while live")

    return DegradationVerdict(should_degrade=bool(reasons), reasons=reasons)


__all__ = ["DegradationVerdict", "LiveRecord", "evaluate_degradation"]
