"""Projection honesty (PRD North Star, §2) — |live Sharpe − paper Sharpe|.

The platform's North Star is that its projections are *honest*: a graduated
strategy's live risk-adjusted return should track what paper promised. This
tracks the gap per strategy; a gap beyond the graduation tolerance is a
projection-honesty breach (an input to de-graduation). Pure.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def projection_honesty(paper_sharpe: float, live_sharpe: float) -> float:
    """The honesty gap |live − paper Sharpe| (lower is better)."""
    return abs(live_sharpe - paper_sharpe)


@dataclass
class HonestyTracker:
    """Per-strategy projection-honesty gaps (the North Star measurement)."""

    gaps: dict[str, float] = field(default_factory=dict)

    def update(self, strategy: str, *, paper_sharpe: float, live_sharpe: float) -> float:
        """Record and return the latest gap for ``strategy``."""
        gap = projection_honesty(paper_sharpe, live_sharpe)
        self.gaps[strategy] = gap
        return gap

    def within_tolerance(self, strategy: str, tolerance: float) -> bool:
        """True if the strategy has no recorded gap, or its gap is within ``tolerance``."""
        gap = self.gaps.get(strategy)
        return gap is None or gap <= tolerance

    def worst(self) -> tuple[str, float] | None:
        """The strategy with the largest honesty gap (or ``None`` if empty)."""
        if not self.gaps:
            return None
        strategy = max(self.gaps, key=lambda name: self.gaps[name])
        return strategy, self.gaps[strategy]


__all__ = ["HonestyTracker", "projection_honesty"]
