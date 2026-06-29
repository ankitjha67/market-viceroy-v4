"""Thin Operator API (PRD §7 subset) — health, kill-switch, decisions, positions.

Single-operator token auth on mutating endpoints; the kill-switch reset is the
Operator-only re-enable path (FR-R2). State (kill-switch, journal, positions
provider) is injected so the app is testable with fakes and wired to the live
loop's components in production.
"""

from __future__ import annotations

import hmac
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from mv.api.strategies import get_strategy, list_strategies
from mv.api.ws import BroadcastHub
from mv.journal.journal import Journal
from mv.risk.kill_switch import KillSwitch

# The browser origin the Command Deck UI is served from (CORS allow-list). An
# explicit origin — never "*", since reads expose the trading posture.
_UI_ORIGIN = os.environ.get("MV_UI_ORIGIN", "http://localhost:3000")

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
    # Graduation (Phase 7): live status per strategy + the Operator-signed handler.
    live_status_provider: Callable[[str], str | None] = field(default=lambda _slug: None)
    graduate_handler: Callable[[str, str], dict[str, Any]] | None = None
    # Command Deck (Phase 8): portfolio summary + per-source health.
    portfolio_provider: Callable[[], dict[str, Any]] = field(default=dict)
    source_health_provider: Callable[[], list[dict[str, Any]]] = field(default=lambda: [])
    # Live dashboard (Phase 10): the continuous loop's equity-curve time series.
    portfolio_history_provider: Callable[[], list[dict[str, Any]]] = field(default=lambda: [])
    # Price chart (Phase 11): recent INR OHLCV candles + volume + BUY/SELL markers.
    ohlcv_provider: Callable[[], dict[str, Any]] = field(
        default=lambda: {"bars": [], "markers": []}
    )
    # Performance panel (Phase 11): live trade stats + equity-curve risk metrics.
    metrics_provider: Callable[[], dict[str, Any]] = field(default=dict)
    # Trade blotter (Phase 11): the journal's closed round trips as display rows.
    trades_provider: Callable[[], list[dict[str, Any]]] = field(default=lambda: [])
    # News & sentiment (Phase 11): live headlines + per-instrument sentiment.
    news_provider: Callable[[], dict[str, Any]] = field(
        default=lambda: {"sentiment": {}, "headlines": []}
    )
    # Phase 9 screens: risk limits + exposures, journal search, read-only config.
    risk_provider: Callable[[], dict[str, Any]] = field(default=dict)
    settings_provider: Callable[[], dict[str, Any]] = field(default=dict)
    # Phase 9 real-time: the loop publishes ticks/decisions/fills/health here.
    hub: BroadcastHub = field(default_factory=BroadcastHub)


def _valid_operator_token(token: str | None, expected: str) -> bool:
    """Constant-time compare of the supplied token against the Operator token."""
    return bool(token) and hmac.compare_digest(token or "", expected)


def create_app(state: ApiState) -> FastAPI:
    """Build the FastAPI app bound to ``state``."""
    # An empty Operator token would let an absent/empty header authenticate — the
    # token guards kill / reset / graduate, so refuse to start without one.
    if not state.operator_token:
        raise ValueError("operator_token must be a non-empty secret")

    app = FastAPI(title="Market Viceroy v4", version="0.1.0")
    # Explicit, non-wildcard CORS: only the Command Deck origin may read the API
    # from a browser. Reads expose positions/equity/journal, so never allow "*".
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[_UI_ORIGIN],
        allow_methods=["GET", "POST"],
        allow_headers=["X-Operator-Token", "Accept", "Content-Type"],
    )

    def require_operator(
        token: Annotated[str | None, Header(alias="X-Operator-Token")] = None,
    ) -> None:
        if not _valid_operator_token(token, state.operator_token):
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
    def postmortem_replay(request: dict[str, Any], _: None = operator) -> dict[str, Any]:
        """Counterfactual replay: re-run with one variable changed (FR-P3).

        Operator-authed: a replay is an expensive re-run, so it is gated like the
        other mutating/compute-heavy actions (no unauthenticated DoS vector).
        """
        if state.replay_provider is None:
            raise HTTPException(status_code=503, detail="replay is not configured")
        return state.replay_provider(request)

    @app.get("/api/v1/arbitrage")
    def arbitrage() -> list[dict[str, Any]]:
        """Arbitrage opportunities + after-cost edge + R/A/G executability (US-011)."""
        return state.arbitrage_provider()

    @app.get("/api/v1/portfolio")
    def portfolio() -> dict[str, Any]:
        """Command Deck summary: equity, day P&L, drawdown, peak (Phase 8)."""
        return state.portfolio_provider()

    @app.get("/api/v1/portfolio/history")
    def portfolio_history() -> list[dict[str, Any]]:
        """Live equity curve: per-tick {ts, equity, day_pnl, decisions, ...} (Phase 10)."""
        return state.portfolio_history_provider()

    @app.get("/api/v1/ohlcv")
    def ohlcv() -> dict[str, Any]:
        """Price chart: recent INR candles + volume + BUY/SELL trade markers (Phase 11)."""
        return state.ohlcv_provider()

    @app.get("/api/v1/metrics")
    def metrics() -> dict[str, Any]:
        """Performance panel: trade stats (win rate / profit factor / …) + risk (Phase 11)."""
        return state.metrics_provider()

    @app.get("/api/v1/trades")
    def trades() -> list[dict[str, Any]]:
        """Trade blotter: closed round trips with entry/exit/P&L/return/duration (Phase 11)."""
        return state.trades_provider()

    @app.get("/api/v1/news")
    def news() -> dict[str, Any]:
        """News & sentiment: recent crypto headlines + per-instrument sentiment (Phase 11)."""
        return state.news_provider()

    @app.get("/api/v1/health/sources")
    def source_health() -> list[dict[str, Any]]:
        """Per-source health: status / quota burn / latency / failover / reconcile."""
        return state.source_health_provider()

    @app.get("/api/v1/risk/limits")
    def risk_limits() -> dict[str, Any]:
        """Risk Console: current hard limits + live exposures (Phase 9)."""
        return state.risk_provider()

    @app.get("/api/v1/journal")
    def journal_search(
        kind: str | None = None,
        q: str | None = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    ) -> list[dict[str, Any]]:
        """Journal Explorer: filter the hash-chained journal by kind + text (Phase 9).

        ``limit`` is clamped to ``[1, 1000]`` so a single request cannot ask the
        server to serialize an unbounded slice.
        """
        needle = q.lower() if q else None
        rows: list[dict[str, Any]] = []
        for entry in state.journal.entries():
            if kind and entry.kind != kind:
                continue
            if needle and needle not in json.dumps(entry.payload).lower():
                continue
            rows.append(
                {
                    "seq": entry.seq,
                    "kind": entry.kind,
                    "ts": entry.ts.isoformat(),
                    "payload": entry.payload,
                }
            )
        return rows[-limit:]

    @app.get("/api/v1/settings")
    def settings() -> dict[str, Any]:
        """Settings: read-only config (ladders, LLM routing, mode) — never secrets."""
        return state.settings_provider()

    @app.websocket("/ws/stream")
    async def stream(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
        """Real-time fan-out of ticks / decisions / fills / source-health (Phase 9).

        Operator-authed before accept: the stream carries the live trade feed, so
        the token is required as a ``?token=`` query param (browsers cannot set
        headers on the WS handshake) and checked constant-time. The UI subscribes
        for low-latency updates and falls back to REST polling on disconnect — so
        this stream is an optimization, never the only path.
        """
        if not _valid_operator_token(token, state.operator_token):
            await websocket.close(code=1008)  # policy violation
            return
        await websocket.accept()
        queue = state.hub.subscribe()
        try:
            while True:
                event = await queue.get()
                await websocket.send_json(event)
        except (WebSocketDisconnect, RuntimeError):
            # A normal client disconnect surfaces from send_json as RuntimeError
            # (ConnectionClosed) in Starlette, not only from receive().
            pass
        finally:
            state.hub.unsubscribe(queue)

    @app.get("/api/v1/positions")
    def positions() -> list[dict[str, Any]]:
        return state.positions_provider()

    @app.get("/api/v1/strategies")
    def strategies() -> list[dict[str, Any]]:
        rows = list_strategies()
        for row in rows:
            row["live_status"] = state.live_status_provider(row["slug"]) or "paper"
        return rows

    @app.post("/api/v1/strategies/{slug}/graduate")
    def graduate(slug: str, operator_id: str, _: None = operator) -> dict[str, Any]:
        """Operator sign-off to promote a strategy to live (FR-P6, BR-005).

        Single-operator-token authed and journaled. Promotes only if the
        strategy is eligible (sustained honest paper record) AND compliance is
        all-clear; otherwise 422 with the blocking reasons. Every attempt —
        success or rejection — is journaled for the audit trail.
        """
        if state.graduate_handler is None:
            raise HTTPException(status_code=503, detail="graduation is not configured")
        result = state.graduate_handler(slug, operator_id)
        state.journal.append("graduation", {"slug": slug, "operator": operator_id, **result})
        if not result.get("graduated", False):
            raise HTTPException(
                status_code=422,
                detail={"slug": slug, "reasons": result.get("reasons", [])},
            )
        return {"slug": slug, **result}

    @app.get("/api/v1/strategies/{slug}")
    def strategy_detail(slug: str) -> dict[str, Any]:
        detail = get_strategy(slug)
        if detail is None:
            raise HTTPException(status_code=404, detail=f"unknown strategy '{slug}'")
        return detail

    return app
