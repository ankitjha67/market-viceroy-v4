"""The LangGraph pipeline state (PRD FR-A1) — the typed channel schema.

Each node writes its stage's record(s) into ``GraphState`` exactly once (a
linear pipeline, so last-write-wins channels — no reducers needed). The
per-invoke inputs (the point-in-time context, the live portfolio state, equity)
are supplied at ``invoke``; the stage outputs accumulate as the graph runs.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

from mv.agents.baseline.runner import GatedDecision
from mv.agents.roster.context import AgentContext
from mv.agents.roster.debate import DebateOutcome
from mv.agents.schemas import AnalystView, ResearchVerdict, TradeDecision
from mv.risk.engine import PortfolioState


class GraphState(TypedDict, total=False):
    """The agent-pipeline state threaded through the LangGraph nodes."""

    # --- per-invoke inputs ---
    ctx: AgentContext
    portfolio_state: PortfolioState
    equity: Decimal

    # --- stage outputs ---
    views: list[AnalystView]
    debate: DebateOutcome
    verdict: ResearchVerdict
    proposed: TradeDecision
    gated: GatedDecision
