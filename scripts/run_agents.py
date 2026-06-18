"""Offline Agent Room demo (Phase 4) — print the journaled agent transcript.

Runs the deterministic LangGraph agent pipeline over one point-in-time feature
snapshot and prints the full glass-box transcript (each analyst's stance/score,
the bull/bear debate, the Research Manager's verdict, the inviolable risk check,
and the Portfolio Manager's Buy/Sell/Hold). No network, no LLM, no Docker — the
deterministic path that backs FR-A9. Pass ``--llm ollama`` only on a machine
with a local Ollama server (offline); the default is fully deterministic.

    uv run python scripts/run_agents.py
    uv run python scripts/run_agents.py --sentiment 0.8 --regime -0.4
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal

from mv.agents.graph import build_agent_graph, run_decision
from mv.agents.roster.context import AgentContext
from mv.journal.journal import Journal
from mv.risk.engine import PortfolioState, RiskEngine
from mv.risk.kill_switch import KillSwitch
from mv.risk.limits import RiskLimits


def _portfolio_state(equity: Decimal) -> PortfolioState:
    return PortfolioState(
        equity=equity,
        peak_equity=equity,
        day_start_equity=equity,
        gross_exposure=Decimal("0"),
        net_exposure=Decimal("0"),
        positions={},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Print one agent-pipeline transcript.")
    parser.add_argument("--instrument", default="BTC/USDT")
    parser.add_argument("--sentiment", type=float, default=None)
    parser.add_argument("--news-sentiment", type=float, default=None)
    parser.add_argument("--regime", type=float, default=None)
    parser.add_argument("--momentum", type=float, default=None)
    parser.add_argument("--equity", type=Decimal, default=Decimal("1000000"))
    args = parser.parse_args()

    features = {
        name: value
        for name, value in (
            ("sentiment", args.sentiment),
            ("news_sentiment", args.news_sentiment),
            ("regime", args.regime),
            ("momentum", args.momentum),
        )
        if value is not None
    }

    journal = Journal()
    risk_engine = RiskEngine(RiskLimits.aggressive(), KillSwitch())
    app = build_agent_graph(journal=journal, risk_engine=risk_engine)

    ts = datetime.now(timezone.utc)
    ctx = AgentContext(
        instrument=args.instrument,
        ts=ts,
        snapshot_id=f"{args.instrument}:{ts.isoformat()}",
        features=features,
    )
    gated = run_decision(
        app, ctx, portfolio_state=_portfolio_state(args.equity), equity=args.equity
    )

    print(f"\nAgent Room transcript for {args.instrument}  (features: {features or 'none'})")
    print("=" * 72)
    for entry in journal.entries():
        payload = entry.payload
        agent = payload.get("agent", "?")
        rationale = payload.get("rationale", "")
        print(f"[{entry.kind:16}] {agent:20} {rationale}")
    print("=" * 72)
    decision = gated.decision
    print(
        f"DECISION: {decision.action}  conviction={decision.conviction:.2f}  "
        f"execute={gated.execute}  approved={gated.risk.approved}"
    )
    if gated.risk.breached_limits:
        print(f"  breached: {', '.join(gated.risk.breached_limits)}")


if __name__ == "__main__":
    main()
