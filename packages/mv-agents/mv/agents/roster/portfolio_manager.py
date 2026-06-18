"""Portfolio Manager (PRD FR-A5) — turns the verdict into a proposed B/S/H.

Maps the Research Manager's net stance to an explicit action and a signed
conviction fraction in ``[-1, 1]`` (``target_size``), with conviction from the
verdict confidence and the dissenting view named. This is the **proposal**;
sizing to a notional and the inviolable risk gate happen next
(:func:`mv.agents.roster.risk.gate`). The PM never sees or overrides risk —
it proposes, the risk engine disposes.
"""

from __future__ import annotations

from decimal import Decimal

from mv.agents.roster.context import AgentContext
from mv.agents.schemas import ResearchVerdict, TradeDecision

_HOLD_THRESHOLD = 0.1


def propose(verdict: ResearchVerdict, ctx: AgentContext) -> TradeDecision:
    """Propose an explicit Buy/Sell/Hold from the research verdict (risk pending)."""
    net = verdict.bull_strength - verdict.bear_strength  # in [-1, 1]

    if net > _HOLD_THRESHOLD:
        action = "BUY"
        target = net
        dissent = f"bear case at {verdict.bear_strength:.2f}"
    elif net < -_HOLD_THRESHOLD:
        action = "SELL"
        target = net
        dissent = f"bull case at {verdict.bull_strength:.2f}"
    else:
        action = "HOLD"
        target = 0.0
        stronger = "bull" if verdict.bull_strength >= verdict.bear_strength else "bear"
        dissent = f"inconclusive debate; {stronger} side marginally ahead"

    rationale = f"verdict {verdict.net_stance} (net {net:+.2f}) -> {action}"
    return TradeDecision(
        agent="portfolio_manager",
        instrument=ctx.instrument,
        ts=ctx.ts,
        snapshot_id=ctx.snapshot_id,
        confidence=verdict.confidence,
        rationale=rationale,
        action=action,  # type: ignore[arg-type]  # narrowed by the branches above
        target_size=Decimal(str(round(target, 6))),
        conviction=verdict.confidence,
        dissent=dissent,
        risk_ref="pending",
        expected_edge_bps_after_cost=None,
    )
