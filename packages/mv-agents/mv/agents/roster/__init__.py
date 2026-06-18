"""The agent roster (PRD FR-A2): deterministic reasoners over point-in-time evidence.

Research Pod (News, Macro, Flow) + Analyst Pod (Fundamentals, Valuation,
Technical, Sentiment) -> AnalystViews; Bull/Bear debate -> DebateTurns; Research
Manager -> ResearchVerdict; Portfolio Manager -> proposed TradeDecision; Risk
Manager -> the inviolable gate. The :mod:`mv.agents.graph` package wires these
into the LangGraph pipeline.
"""

from __future__ import annotations

from mv.agents.roster.analysts import analyst_agents, run_analysts
from mv.agents.roster.context import AgentContext
from mv.agents.roster.debate import DebateOutcome, run_debate
from mv.agents.roster.portfolio_manager import propose
from mv.agents.roster.research_manager import adjudicate
from mv.agents.roster.risk import gate

__all__ = [
    "AgentContext",
    "DebateOutcome",
    "adjudicate",
    "analyst_agents",
    "gate",
    "propose",
    "run_analysts",
    "run_debate",
]
