"""The LangGraph agent pipeline (PRD §4.5, FR-A1/A3) — Research → ... → B/S/H.

Wires the deterministic roster into a stateful LangGraph ``StateGraph``:

    analysts -> debate -> research_manager -> portfolio_manager -> risk

Every node **journals its record(s)** as it runs (FR-A3/J2), so the journal is
the persistent, tamper-evident decision log (FR-A1). The Risk node is the
inviolable gate — a vetoed proposal yields no order, journaled with the breach.
The graph result is the same :class:`~mv.agents.baseline.runner.GatedDecision`
the paper loop already consumes, so the agent pipeline is a drop-in for the
Phase-1 ensemble. Deterministic: identical context -> identical decision.

LangGraph is untyped (mypy override), so the compiled graph is ``Any`` here —
the same pattern the NautilusTrader bridge uses.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Protocol

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from mv.agents.baseline.runner import GatedDecision
from mv.agents.graph.state import GraphState
from mv.agents.roster.analysts import run_analysts
from mv.agents.roster.context import AgentContext
from mv.agents.roster.debate import run_debate
from mv.agents.roster.portfolio_manager import propose
from mv.agents.roster.research_manager import adjudicate
from mv.agents.roster.risk import gate
from mv.risk.engine import PortfolioState, RiskEngine


class JournalSink(Protocol):
    """The minimal append-only journal contract the graph writes to."""

    def append(self, kind: str, payload: Mapping[str, Any]) -> Any:
        """Append one record of ``kind`` carrying ``payload``."""
        ...


def build_agent_graph(*, journal: JournalSink, risk_engine: RiskEngine) -> Any:
    """Compile the agent pipeline; nodes journal to ``journal`` and gate on ``risk_engine``.

    ``journal`` and ``risk_engine`` are stable across decisions and captured in
    the node closures; the per-bar inputs (context, portfolio state, equity)
    arrive in the invocation state.
    """

    def _analysts(state: GraphState) -> dict[str, Any]:
        views = run_analysts(state["ctx"])
        for view in views:
            journal.append("analyst_view", view.model_dump(mode="json"))
        return {"views": views}

    def _debate(state: GraphState) -> dict[str, Any]:
        outcome = run_debate(state["views"], state["ctx"])
        for turn in outcome.turns:
            journal.append("debate_turn", turn.model_dump(mode="json"))
        return {"debate": outcome}

    def _research_manager(state: GraphState) -> dict[str, Any]:
        verdict = adjudicate(state["debate"], state["ctx"])
        journal.append("research_verdict", verdict.model_dump(mode="json"))
        return {"verdict": verdict}

    def _portfolio_manager(state: GraphState) -> dict[str, Any]:
        return {"proposed": propose(state["verdict"], state["ctx"])}

    def _risk(state: GraphState) -> dict[str, Any]:
        gated = gate(
            state["proposed"],
            state["ctx"],
            risk_engine=risk_engine,
            portfolio_state=state["portfolio_state"],
            equity=state["equity"],
        )
        # §5 order: RiskAssessment then the final (sized, risk-ref'd) TradeDecision.
        journal.append("risk_assessment", gated.risk.model_dump(mode="json"))
        journal.append("decision", gated.decision.model_dump(mode="json"))
        return {"gated": gated}

    graph: Any = StateGraph(GraphState)
    graph.add_node("analysts", _analysts)
    graph.add_node("debate", _debate)
    graph.add_node("research_manager", _research_manager)
    graph.add_node("portfolio_manager", _portfolio_manager)
    graph.add_node("risk", _risk)

    graph.add_edge(START, "analysts")
    graph.add_edge("analysts", "debate")
    graph.add_edge("debate", "research_manager")
    graph.add_edge("research_manager", "portfolio_manager")
    graph.add_edge("portfolio_manager", "risk")
    graph.add_edge("risk", END)

    return graph.compile(checkpointer=MemorySaver())


def run_decision(
    app: Any,
    ctx: AgentContext,
    *,
    portfolio_state: PortfolioState,
    equity: Decimal,
    thread_id: str | None = None,
) -> GatedDecision:
    """Run the agent pipeline over one context; return the gated Buy/Sell/Hold.

    The records are journaled as a side effect of the run (see
    :func:`build_agent_graph`). ``thread_id`` keys the checkpointer; it defaults
    to the context's ``snapshot_id`` so each decision is its own thread.
    """
    config = {"configurable": {"thread_id": thread_id or ctx.snapshot_id}}
    state: GraphState = {"ctx": ctx, "portfolio_state": portfolio_state, "equity": equity}
    out: dict[str, Any] = app.invoke(state, config=config)
    gated: GatedDecision = out["gated"]
    return gated
