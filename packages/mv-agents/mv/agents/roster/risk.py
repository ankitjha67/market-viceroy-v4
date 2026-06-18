"""Risk Manager node (PRD FR-A6/R2) — the inviolable veto, reusing the engine.

The Risk Manager *is* the Phase-1 risk engine: it sizes the PM's proposal and
checks it against the same inviolable limits (kill-switch, daily-loss, drawdown,
exposure) via the shared :func:`mv.agents.baseline.runner.gate_proposed_trade`.
No agent or autonomy setting can re-enable a limit — only the Operator. A vetoed
decision produces no order, journaled with the breached limit.
"""

from __future__ import annotations

from decimal import Decimal

from mv.agents.baseline.runner import GatedDecision, gate_proposed_trade
from mv.agents.roster.context import AgentContext
from mv.agents.schemas import TradeDecision
from mv.risk.engine import PortfolioState, RiskEngine


def gate(
    proposed: TradeDecision,
    ctx: AgentContext,
    *,
    risk_engine: RiskEngine,
    portfolio_state: PortfolioState,
    equity: Decimal,
) -> GatedDecision:
    """Size + risk-gate the PM proposal; return the gated decision + assessment."""
    return gate_proposed_trade(
        proposed,
        symbol=ctx.instrument,
        ts=ctx.ts,
        snapshot_id=ctx.snapshot_id,
        equity=equity,
        risk_engine=risk_engine,
        portfolio_state=portfolio_state,
    )
