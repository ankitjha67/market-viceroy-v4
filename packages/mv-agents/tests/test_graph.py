"""End-to-end tests for the LangGraph agent pipeline (deterministic, no LLM)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from mv.agents.graph import build_agent_graph, run_decision
from mv.agents.roster.context import AgentContext
from mv.journal.journal import Journal
from mv.risk.engine import PortfolioState, RiskEngine
from mv.risk.kill_switch import KillSwitch
from mv.risk.limits import RiskLimits

_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _ctx(snapshot: str = "snap-1", **features: float) -> AgentContext:
    return AgentContext(
        instrument="BTC/USDT",
        ts=_TS,
        snapshot_id=snapshot,
        features=dict(features),
    )


def _state(equity: Decimal) -> PortfolioState:
    return PortfolioState(
        equity=equity,
        peak_equity=equity,
        day_start_equity=equity,
        gross_exposure=Decimal("0"),
        net_exposure=Decimal("0"),
        positions={},
    )


def _engine(kill: KillSwitch | None = None) -> RiskEngine:
    return RiskEngine(RiskLimits.aggressive(), kill or KillSwitch())


def test_graph_produces_buy_and_journals_full_transcript() -> None:
    journal = Journal()
    app = build_agent_graph(journal=journal, risk_engine=_engine())
    gated = run_decision(
        app,
        _ctx(sentiment=0.9, news_sentiment=0.8),
        portfolio_state=_state(Decimal("1000000")),
        equity=Decimal("1000000"),
    )
    assert gated.decision.action == "BUY"
    assert gated.execute is True
    assert gated.decision.risk_ref.startswith("risk:")

    # The journal carries the whole debated, risk-checked transcript (FR-A3/J2).
    kinds = [e.kind for e in journal.entries()]
    assert kinds.count("analyst_view") == 7
    assert kinds.count("debate_turn") == 2
    assert "research_verdict" in kinds
    assert "risk_assessment" in kinds
    assert "decision" in kinds
    # §5 order: risk assessment is journaled before the final decision.
    assert kinds.index("risk_assessment") < kinds.index("decision")
    journal.verify()  # raises if the hash chain is broken


def test_graph_holds_on_balanced_evidence() -> None:
    journal = Journal()
    app = build_agent_graph(journal=journal, risk_engine=_engine())
    gated = run_decision(
        app,
        _ctx(sentiment=0.5, regime=-0.5),
        portfolio_state=_state(Decimal("1000000")),
        equity=Decimal("1000000"),
    )
    assert gated.decision.action == "HOLD"
    assert gated.execute is False


def test_graph_risk_veto_produces_no_order() -> None:
    kill = KillSwitch()
    kill.trip(reason="operator halt")
    journal = Journal()
    app = build_agent_graph(journal=journal, risk_engine=_engine(kill))
    gated = run_decision(
        app,
        _ctx(sentiment=0.9, news_sentiment=0.8),
        portfolio_state=_state(Decimal("1000000")),
        equity=Decimal("1000000"),
    )
    assert gated.execute is False
    assert gated.risk.approved is False
    assert gated.risk.breached_limits
    # Even a vetoed decision is journaled (no-trade is a decision).
    assert "decision" in [e.kind for e in journal.entries()]


def test_graph_is_deterministic() -> None:
    app = build_agent_graph(journal=Journal(), risk_engine=_engine())
    state, equity = _state(Decimal("1000000")), Decimal("1000000")
    first = run_decision(app, _ctx("a", sentiment=0.7), portfolio_state=state, equity=equity)
    second = run_decision(app, _ctx("b", sentiment=0.7), portfolio_state=state, equity=equity)
    assert first.decision.action == second.decision.action
    assert first.decision.target_size == second.decision.target_size
