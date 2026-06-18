"""Research Manager (PRD FR-A4) — adjudicates the debate into a thesis verdict.

Weighs ``bull_strength`` against ``bear_strength`` to a net stance and a
confidence equal to the strength gap, producing the
:class:`~mv.agents.schemas.ResearchVerdict` the Portfolio Manager acts on.
Deterministic.
"""

from __future__ import annotations

from mv.agents.roster.context import AgentContext, stance_from_score
from mv.agents.roster.debate import DebateOutcome
from mv.agents.schemas import ResearchVerdict

_NEUTRAL_BAND = 0.1


def adjudicate(debate: DebateOutcome, ctx: AgentContext) -> ResearchVerdict:
    """Synthesize the debate into a net-stance thesis with confidence = the gap."""
    net = debate.bull_strength - debate.bear_strength  # in [-1, 1]
    net_stance = stance_from_score(net, neutral_band=_NEUTRAL_BAND)
    confidence = min(1.0, abs(net))
    thesis = (
        f"bull {debate.bull_strength:.2f} vs bear {debate.bear_strength:.2f} "
        f"(net {net:+.2f}) -> {net_stance}"
    )
    return ResearchVerdict(
        agent="research_manager",
        instrument=ctx.instrument,
        ts=ctx.ts,
        snapshot_id=ctx.snapshot_id,
        confidence=confidence,
        rationale=thesis,
        thesis=thesis,
        net_stance=net_stance,
        bull_strength=debate.bull_strength,
        bear_strength=debate.bear_strength,
    )
