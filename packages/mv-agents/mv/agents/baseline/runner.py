"""Run the strategies on a price window and produce a risk-gated decision.

The pure heart of the MVP loop (no NautilusTrader): runs every strategy's
``generate_signals`` on the rolling window, ensembles their latest weights into
a Buy/Sell/Hold, sizes it against equity, and gates it through the inviolable
risk engine. Returns a :class:`GatedDecision` the loop journals and (if
approved) executes. Pure and deterministic, so it is unit-tested without any
exchange or engine.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol, runtime_checkable

import pandas as pd
from mv.agents.baseline.pipeline import StrategySignal, ensemble_decision
from mv.agents.schemas import RiskAssessment, TradeDecision
from mv.risk.engine import PortfolioState, ProposedTrade, RiskEngine, RiskResult


@runtime_checkable
class SignalStrategy(Protocol):
    """Minimal strategy contract (alphakit ``StrategyProtocol`` satisfies it)."""

    name: str

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame: ...


@dataclass(frozen=True, slots=True)
class GatedDecision:
    """The decision plus its risk verdict and what to execute.

    ``signals`` carries the per-strategy votes that produced the ensemble (empty
    on the agent-graph path, which journals its own transcript). The loop journals
    them as a ``signals`` record so the glass-box log shows every strategy's
    weight, not just the combined Buy/Sell/Hold.
    """

    decision: TradeDecision
    risk: RiskAssessment
    execute: bool
    side: Literal["BUY", "SELL"] | None
    notional: Decimal
    signals: tuple[StrategySignal, ...] = ()


def strategy_signals(
    strategies: Sequence[SignalStrategy], window: pd.DataFrame, symbol: str
) -> list[StrategySignal]:
    """Latest per-strategy signal weight for ``symbol`` over ``window``."""
    signals: list[StrategySignal] = []
    for strategy in strategies:
        weights = strategy.generate_signals(window)
        if symbol in weights.columns and len(weights) > 0:
            latest = weights[symbol].iloc[-1]
            weight = Decimal("0") if pd.isna(latest) else Decimal(str(float(latest)))
        else:
            weight = Decimal("0")
        signals.append(StrategySignal(strategy=strategy.name, weight=weight))
    return signals


def _risk_assessment(
    result: RiskResult, *, instrument: str, ts: datetime, snapshot_id: str
) -> RiskAssessment:
    return RiskAssessment(
        agent="risk_manager",
        instrument=instrument,
        ts=ts,
        snapshot_id=snapshot_id,
        confidence=1.0,
        rationale=result.notes,
        approved=result.approved,
        breached_limits=list(result.breached_limits),
        max_size_allowed=result.max_size_allowed,
        notes=result.notes,
    )


def gate_proposed_trade(
    proposed: TradeDecision,
    *,
    symbol: str,
    ts: datetime,
    snapshot_id: str,
    equity: Decimal,
    risk_engine: RiskEngine,
    portfolio_state: PortfolioState,
) -> GatedDecision:
    """Size a proposed signed-fraction decision and gate it through the risk engine.

    This is the single sizing + inviolable-risk path shared by the Phase-1
    ensemble baseline (:func:`decide`) and the Phase-4 agent graph: a proposal
    with ``target_size`` a signed conviction fraction in ``[-1, 1]`` is sized to
    a per-position-capped notional and checked against the risk engine. The risk
    engine remains the inviolable gate (kill-switch, daily-loss, drawdown,
    exposure) — no proposal can bypass it.
    """
    if proposed.action == "HOLD":
        risk = RiskAssessment(
            agent="risk_manager",
            instrument=symbol,
            ts=ts,
            snapshot_id=snapshot_id,
            confidence=1.0,
            rationale="no order (HOLD)",
            approved=True,
            breached_limits=[],
            max_size_allowed=Decimal("0"),
            notes="no order (HOLD)",
        )
        return GatedDecision(proposed, risk, execute=False, side=None, notional=Decimal("0"))

    side: Literal["BUY", "SELL"] = "BUY" if proposed.target_size > 0 else "SELL"
    # Size within the per-position cap: a full-conviction proposal (|w|=1)
    # targets exactly max_position_pct of equity.
    target_fraction = proposed.target_size * risk_engine.limits.max_position_pct
    notional = (target_fraction * equity).copy_abs()
    result = risk_engine.check(ProposedTrade(symbol, side, notional), portfolio_state)
    risk = _risk_assessment(result, instrument=symbol, ts=ts, snapshot_id=snapshot_id)
    decision = proposed.model_copy(
        update={"risk_ref": f"risk:{snapshot_id}", "target_size": target_fraction}
    )
    return GatedDecision(decision, risk, execute=result.approved, side=side, notional=notional)


def decide(
    strategies: Sequence[SignalStrategy],
    window: pd.DataFrame,
    *,
    symbol: str,
    ts: datetime,
    snapshot_id: str,
    equity: Decimal,
    risk_engine: RiskEngine,
    portfolio_state: PortfolioState,
    hold_threshold: Decimal = Decimal("0.05"),
) -> GatedDecision:
    """Run strategies -> ensemble -> size -> risk gate; return the gated decision."""
    signals = strategy_signals(strategies, window, symbol)
    proposed = ensemble_decision(
        signals,
        instrument=symbol,
        ts=ts,
        snapshot_id=snapshot_id,
        hold_threshold=hold_threshold,
    )
    gated = gate_proposed_trade(
        proposed,
        symbol=symbol,
        ts=ts,
        snapshot_id=snapshot_id,
        equity=equity,
        risk_engine=risk_engine,
        portfolio_state=portfolio_state,
    )
    # Carry the per-strategy votes so the loop can journal the full glass-box log.
    return replace(gated, signals=tuple(signals))
