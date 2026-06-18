"""Unit tests for the deterministic agent roster (analysts -> debate -> PM -> risk)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from mv.agents.baseline.pipeline import StrategySignal
from mv.agents.roster import (
    AgentContext,
    adjudicate,
    propose,
    run_analysts,
    run_debate,
)
from mv.agents.roster.analysts import analyst_agents, technical_analyst
from mv.agents.roster.risk import gate
from mv.risk.engine import PortfolioState, RiskEngine
from mv.risk.kill_switch import KillSwitch
from mv.risk.limits import RiskLimits

_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _engine(kill: KillSwitch | None = None) -> RiskEngine:
    return RiskEngine(RiskLimits.aggressive(), kill or KillSwitch())


def _ctx(**features: float) -> AgentContext:
    return AgentContext(
        instrument="BTC/USDT",
        ts=_TS,
        snapshot_id="snap-1",
        features=dict(features),
        signals=(),
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


# ---- analysts -----------------------------------------------------------------


def test_run_analysts_emits_full_roster() -> None:
    views = run_analysts(_ctx(sentiment=0.5))
    agents = {v.agent for v in views}
    assert agents == set(analyst_agents())
    assert len(views) == 7


def test_missing_feature_is_neutral_zero_confidence() -> None:
    # A crypto pair with no fundamentals coverage -> honest neutral.
    views = {v.agent: v for v in run_analysts(_ctx())}
    fundamentals = views["fundamentals_analyst"]
    assert fundamentals.stance == "neutral"
    assert fundamentals.score == 0.0
    assert fundamentals.confidence == 0.0
    assert "no fundamental_score coverage" in fundamentals.rationale
    assert fundamentals.key_factors == []


def test_present_feature_drives_stance() -> None:
    views = {v.agent: v for v in run_analysts(_ctx(sentiment=0.8, regime=-0.6))}
    assert views["sentiment_analyst"].stance == "bullish"
    assert views["sentiment_analyst"].score == 0.8
    assert views["macro_analyst"].stance == "bearish"
    assert views["macro_analyst"].score == -0.6


def test_feature_score_is_clipped() -> None:
    views = {v.agent: v for v in run_analysts(_ctx(sentiment=5.0))}
    assert views["sentiment_analyst"].score == 1.0


def test_technical_analyst_uses_strategy_ensemble() -> None:
    ctx = AgentContext(
        instrument="BTC/USDT",
        ts=_TS,
        snapshot_id="snap-1",
        signals=(
            StrategySignal("ema_cross", Decimal("1.0")),
            StrategySignal("rsi_reversion", Decimal("-0.2")),
        ),
    )
    view = technical_analyst(ctx)
    assert view.stance == "bullish"
    assert view.score == 0.4  # mean(1.0, -0.2)
    assert "ema_cross" in view.key_factors


def test_technical_analyst_falls_back_to_momentum() -> None:
    view = technical_analyst(_ctx(momentum=0.3))
    assert view.score == 0.3
    assert view.key_factors == ["momentum"]


# ---- debate + research manager ------------------------------------------------


def test_debate_strengths_normalize() -> None:
    views = run_analysts(_ctx(sentiment=0.6, news_sentiment=0.4, regime=-0.5))
    outcome = run_debate(views, _ctx())
    assert outcome.bull_strength + outcome.bear_strength == 1.0
    assert outcome.bull_strength > outcome.bear_strength
    sides = {t.side for t in outcome.turns}
    assert sides == {"bull", "bear"}


def test_all_neutral_debate_is_zero() -> None:
    outcome = run_debate(run_analysts(_ctx()), _ctx())
    assert outcome.bull_strength == 0.0
    assert outcome.bear_strength == 0.0


def test_research_manager_net_stance() -> None:
    views = run_analysts(_ctx(sentiment=0.9, news_sentiment=0.7))
    verdict = adjudicate(run_debate(views, _ctx()), _ctx())
    assert verdict.net_stance == "bullish"
    assert verdict.bull_strength == 1.0
    assert verdict.bear_strength == 0.0


# ---- portfolio manager + risk gate -------------------------------------------


def test_pm_proposes_buy_on_bullish_verdict() -> None:
    views = run_analysts(_ctx(sentiment=0.9, news_sentiment=0.8))
    verdict = adjudicate(run_debate(views, _ctx()), _ctx())
    decision = propose(verdict, _ctx())
    assert decision.action == "BUY"
    assert decision.target_size > 0
    assert decision.risk_ref == "pending"
    assert "bear case" in decision.dissent


def test_pm_proposes_sell_on_bearish_verdict() -> None:
    views = run_analysts(_ctx(sentiment=-0.9, news_sentiment=-0.8))
    verdict = adjudicate(run_debate(views, _ctx()), _ctx())
    decision = propose(verdict, _ctx())
    assert decision.action == "SELL"
    assert decision.target_size < 0
    assert "bull case" in decision.dissent


def test_pm_holds_on_balanced_verdict() -> None:
    views = run_analysts(_ctx(sentiment=0.5, regime=-0.5))
    verdict = adjudicate(run_debate(views, _ctx()), _ctx())
    decision = propose(verdict, _ctx())
    assert decision.action == "HOLD"
    assert decision.target_size == Decimal("0")


def test_risk_gate_approves_within_limits() -> None:
    views = run_analysts(_ctx(sentiment=0.9, news_sentiment=0.8))
    verdict = adjudicate(run_debate(views, _ctx()), _ctx())
    proposed = propose(verdict, _ctx())
    engine = _engine()
    gated = gate(
        proposed,
        _ctx(),
        risk_engine=engine,
        portfolio_state=_state(Decimal("1000000")),
        equity=Decimal("1000000"),
    )
    assert gated.execute is True
    assert gated.side == "BUY"
    assert gated.risk.approved is True
    # target_size was sized within the per-position cap.
    assert gated.decision.target_size <= engine.limits.max_position_pct


def test_risk_gate_vetoes_when_kill_switch_active() -> None:
    views = run_analysts(_ctx(sentiment=0.9, news_sentiment=0.8))
    verdict = adjudicate(run_debate(views, _ctx()), _ctx())
    proposed = propose(verdict, _ctx())
    kill = KillSwitch()
    kill.trip(reason="operator test")
    gated = gate(
        proposed,
        _ctx(),
        risk_engine=_engine(kill),
        portfolio_state=_state(Decimal("1000000")),
        equity=Decimal("1000000"),
    )
    assert gated.execute is False
    assert gated.risk.approved is False
    assert gated.risk.breached_limits
