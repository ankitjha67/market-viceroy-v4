"""Thin Operator API (PRD §7 subset) — health, kill-switch, decisions, positions.

Single-operator token auth on mutating endpoints; the kill-switch reset is the
Operator-only re-enable path (FR-R2). State (kill-switch, journal, positions
provider) is injected so the app is testable with fakes and wired to the live
loop's components in production.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException
from mv.api.strategies import get_strategy, list_strategies
from mv.journal.journal import Journal
from mv.risk.kill_switch import KillSwitch

# The agent-pipeline record kinds the graph journals, in §5 pipeline order.
_AGENT_RECORD_KINDS = (
    "analyst_view",
    "debate_turn",
    "research_verdict",
    "risk_assessment",
    "decision",
)


@dataclass
class ApiState:
    """The components the API operates on."""

    kill_switch: KillSwitch
    journal: Journal
    operator_token: str
    positions_provider: Callable[[], list[dict[str, Any]]] = field(default=lambda: [])
    # Post-Mortem Room providers (Phase 5). Injected so the API stays decoupled
    # from mv-postmortem and is testable with fakes; the runner wires the real
    # attribution / taxonomy / ledger / replay engines in.
    attribution_provider: Callable[[str], dict[str, Any] | None] = field(default=lambda _id: None)
    mistakes_provider: Callable[[], dict[str, Any]] = field(default=dict)
    improvements_provider: Callable[[], list[dict[str, Any]]] = field(default=lambda: [])
    replay_provider: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    # Arbitrage Monitor (Phase 6): ranked opportunities + after-cost edge + R/A/G.
    arbitrage_provider: Callable[[], list[dict[str, Any]]] = field(default=lambda: [])


def create_app(state: ApiState) -> FastAPI:
    """Build the FastAPI app bound to ``state``."""
    app = FastAPI(title="Market Viceroy v4", version="0.1.0")

    def require_operator(
        token: Annotated[str | None, Header(alias="X-Operator-Token")] = None,
    ) -> None:
        if token != state.operator_token:
            raise HTTPException(status_code=401, detail="invalid or missing Operator token")

    operator = Depends(require_operator)

    @app.get("/api/v1/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "kill_switch_tripped": state.kill_switch.is_tripped(),
            "journal_length": state.journal.length,
        }

    @app.post("/api/v1/risk/kill")
    def kill(reason: str = "manual", _: None = operator) -> dict[str, Any]:
        event = state.kill_switch.trip(reason=reason)
        return {"action": event.action, "reason": event.reason}

    @app.post("/api/v1/risk/reset")
    def reset(operator_id: str, reason: str = "", _: None = operator) -> dict[str, Any]:
        event = state.kill_switch.reset(operator=operator_id, reason=reason)
        return {"action": event.action, "operator": event.operator}

    @app.get("/api/v1/decisions")
    def decisions() -> list[dict[str, Any]]:
        return [
            {"seq": entry.seq, "ts": entry.ts.isoformat(), "payload": entry.payload}
            for entry in state.journal.entries()
            if entry.kind == "decision"
        ]

    # ``:path`` so instrument-bearing snapshot ids (e.g. "BTC/USDT:<ts>") match.
    @app.get("/api/v1/decisions/{snapshot_id:path}/agents")
    def decision_agents(snapshot_id: str) -> dict[str, Any]:
        """The Agent Room: the full journaled pipeline for one decision.

        Returns every agent record sharing ``snapshot_id`` in pipeline order
        (analyst views -> debate turns -> research verdict -> risk assessment ->
        PM decision) — the "fund in a glass box" the UI renders (Phase 8).
        """
        pipeline = [
            {
                "seq": entry.seq,
                "kind": entry.kind,
                "ts": entry.ts.isoformat(),
                "payload": entry.payload,
            }
            for entry in state.journal.entries()
            if entry.kind in _AGENT_RECORD_KINDS and entry.payload.get("snapshot_id") == snapshot_id
        ]
        if not pipeline:
            raise HTTPException(status_code=404, detail=f"no agent records for '{snapshot_id}'")
        return {"snapshot_id": snapshot_id, "pipeline": pipeline}

    @app.get("/api/v1/trades/{trade_id}/attribution")
    def trade_attribution(trade_id: str) -> dict[str, Any]:
        """Causal PnL decomposition for one closed trade (FR-P1)."""
        attribution = state.attribution_provider(trade_id)
        if attribution is None:
            raise HTTPException(status_code=404, detail=f"no attribution for trade '{trade_id}'")
        return attribution

    @app.get("/api/v1/postmortem/mistakes")
    def postmortem_mistakes() -> dict[str, Any]:
        """Mistake-taxonomy trends: per-category frequency + cumulative cost (FR-P2)."""
        return state.mistakes_provider()

    @app.get("/api/v1/postmortem/improvements")
    def postmortem_improvements() -> list[dict[str, Any]]:
        """The improvement ledger: every adjustment + before/after metrics (FR-P4)."""
        return state.improvements_provider()

    @app.post("/api/v1/postmortem/replay")
    def postmortem_replay(request: dict[str, Any]) -> dict[str, Any]:
        """Counterfactual replay: re-run with one variable changed (FR-P3)."""
        if state.replay_provider is None:
            raise HTTPException(status_code=503, detail="replay is not configured")
        return state.replay_provider(request)

    @app.get("/api/v1/arbitrage")
    def arbitrage() -> list[dict[str, Any]]:
        """Arbitrage opportunities + after-cost edge + R/A/G executability (US-011)."""
        return state.arbitrage_provider()

    @app.get("/api/v1/positions")
    def positions() -> list[dict[str, Any]]:
        return state.positions_provider()

    @app.get("/api/v1/strategies")
    def strategies() -> list[dict[str, Any]]:
        return list_strategies()

    @app.get("/api/v1/strategies/{slug}")
    def strategy_detail(slug: str) -> dict[str, Any]:
        detail = get_strategy(slug)
        if detail is None:
            raise HTTPException(status_code=404, detail=f"unknown strategy '{slug}'")
        return detail

    return app
