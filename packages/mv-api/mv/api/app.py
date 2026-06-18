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


@dataclass
class ApiState:
    """The components the API operates on."""

    kill_switch: KillSwitch
    journal: Journal
    operator_token: str
    positions_provider: Callable[[], list[dict[str, Any]]] = field(default=lambda: [])


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
