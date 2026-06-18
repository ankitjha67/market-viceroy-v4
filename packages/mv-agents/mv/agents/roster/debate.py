"""Bull vs Bear researchers (PRD FR-A4) — a deterministic debate over the views.

The Bull marshals every bullish-leaning analyst view into a claim; the Bear does
the symmetric. The evidence mass on each side (sum of positive vs negative
scores) is normalized into ``bull_strength`` / ``bear_strength`` in ``[0, 1]``
(they sum to 1, or both 0 when every analyst is neutral) — the inputs the
Research Manager adjudicates.
"""

from __future__ import annotations

from dataclasses import dataclass

from mv.agents.roster.context import AgentContext
from mv.agents.schemas import AnalystView, DebateTurn


@dataclass(frozen=True, slots=True)
class DebateOutcome:
    """The debate transcript plus the normalized side strengths."""

    turns: list[DebateTurn]
    bull_strength: float
    bear_strength: float


def _side_strengths(views: list[AnalystView]) -> tuple[float, float]:
    bull_mass = sum(max(0.0, v.score) for v in views)
    bear_mass = sum(max(0.0, -v.score) for v in views)
    total = bull_mass + bear_mass
    if total == 0.0:
        return 0.0, 0.0
    return bull_mass / total, bear_mass / total


def _turn(
    *, agent: str, side: str, ctx: AgentContext, claim: str, refs: list[str], strength: float
) -> DebateTurn:
    return DebateTurn(
        agent=agent,
        instrument=ctx.instrument,
        ts=ctx.ts,
        snapshot_id=ctx.snapshot_id,
        confidence=strength,
        rationale=claim,
        side="bull" if side == "bull" else "bear",
        claim=claim,
        evidence_refs=refs,
    )


def run_debate(views: list[AnalystView], ctx: AgentContext) -> DebateOutcome:
    """Run the bull/bear debate over the analyst views; return turns + strengths."""
    bull_strength, bear_strength = _side_strengths(views)

    bulls = sorted((v for v in views if v.score > 0), key=lambda v: v.score, reverse=True)
    bears = sorted((v for v in views if v.score < 0), key=lambda v: v.score)

    bull_refs = [v.agent for v in bulls]
    bear_refs = [v.agent for v in bears]
    bull_claim = (
        "bullish evidence from " + ", ".join(bull_refs)
        if bulls
        else "no bullish evidence; the long case is weak"
    )
    bear_claim = (
        "bearish evidence from " + ", ".join(bear_refs)
        if bears
        else "no bearish evidence; the short case is weak"
    )

    turns = [
        _turn(
            agent="bull_researcher",
            side="bull",
            ctx=ctx,
            claim=bull_claim,
            refs=bull_refs,
            strength=bull_strength,
        ),
        _turn(
            agent="bear_researcher",
            side="bear",
            ctx=ctx,
            claim=bear_claim,
            refs=bear_refs,
            strength=bear_strength,
        ),
    ]
    return DebateOutcome(turns=turns, bull_strength=bull_strength, bear_strength=bear_strength)
