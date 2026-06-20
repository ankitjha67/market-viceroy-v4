"""Unit tests for the thin Operator API (TestClient + fakes; US-007 surface)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from mv.api.app import ApiState, create_app
from mv.journal.journal import Journal
from mv.risk.kill_switch import KillSwitch

_TOKEN = "operator-secret"


def _client() -> tuple[TestClient, KillSwitch, Journal]:
    kill = KillSwitch()
    journal = Journal()
    journal.append("decision", {"action": "BUY", "instrument": "BTC/USDT"})
    state = ApiState(
        kill_switch=kill,
        journal=journal,
        operator_token=_TOKEN,
        positions_provider=lambda: [{"symbol": "BTC/USDT", "qty": "0.5"}],
    )
    return TestClient(create_app(state)), kill, journal


def test_health() -> None:
    client, _, _ = _client()
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["kill_switch_tripped"] is False
    assert body["journal_length"] == 1


def test_kill_requires_operator_token() -> None:
    client, kill, _ = _client()
    assert client.post("/api/v1/risk/kill").status_code == 401
    assert kill.is_tripped() is False


def test_operator_can_kill_and_reset() -> None:
    client, kill, _ = _client()
    headers = {"X-Operator-Token": _TOKEN}
    resp = client.post("/api/v1/risk/kill", params={"reason": "runaway"}, headers=headers)
    assert resp.status_code == 200
    assert kill.is_tripped() is True

    resp = client.post("/api/v1/risk/reset", params={"operator_id": "ankit"}, headers=headers)
    assert resp.status_code == 200
    assert kill.is_tripped() is False


def test_wrong_token_rejected() -> None:
    client, _, _ = _client()
    resp = client.post("/api/v1/risk/kill", headers={"X-Operator-Token": "wrong"})
    assert resp.status_code == 401


def test_decisions_and_positions() -> None:
    client, _, _ = _client()
    decisions = client.get("/api/v1/decisions").json()
    assert len(decisions) == 1
    assert decisions[0]["payload"]["action"] == "BUY"

    positions = client.get("/api/v1/positions").json()
    assert positions[0]["symbol"] == "BTC/USDT"


def test_arbitrage_endpoint() -> None:
    state = ApiState(
        kill_switch=KillSwitch(),
        journal=Journal(),
        operator_token=_TOKEN,
        arbitrage_provider=lambda: [
            {"kind": "cross_exchange", "after_cost_edge_bps": "12", "executability": "green"},
            {"kind": "cross_border", "after_cost_edge_bps": "200", "executability": "red"},
        ],
    )
    client = TestClient(create_app(state))
    opportunities = client.get("/api/v1/arbitrage").json()
    assert len(opportunities) == 2
    assert opportunities[0]["executability"] == "green"
    # Cross-border is surfaced but flagged non-executable.
    assert opportunities[1]["executability"] == "red"


def test_arbitrage_empty_by_default() -> None:
    client, _, _ = _client()
    assert client.get("/api/v1/arbitrage").json() == []


def test_portfolio_and_source_health_endpoints() -> None:
    state = ApiState(
        kill_switch=KillSwitch(),
        journal=Journal(),
        operator_token=_TOKEN,
        portfolio_provider=lambda: {
            "equity": "1000000",
            "day_pnl": "1250.50",
            "drawdown": "0.02",
            "peak_equity": "1010000",
        },
        source_health_provider=lambda: [
            {"source": "ccxt:binance", "domain": "crypto.prices", "status": "green"}
        ],
    )
    client = TestClient(create_app(state))
    portfolio = client.get("/api/v1/portfolio").json()
    assert portfolio["equity"] == "1000000"
    sources = client.get("/api/v1/health/sources").json()
    assert sources[0]["status"] == "green"


def test_portfolio_empty_by_default() -> None:
    client, _, _ = _client()
    assert client.get("/api/v1/portfolio").json() == {}
    assert client.get("/api/v1/health/sources").json() == []


def _graduation_client(handler: object) -> tuple[TestClient, Journal]:
    journal = Journal()
    state = ApiState(
        kill_switch=KillSwitch(),
        journal=journal,
        operator_token=_TOKEN,
        graduate_handler=handler,  # type: ignore[arg-type]
    )
    return TestClient(create_app(state)), journal


def test_graduate_requires_operator_token() -> None:
    client, _ = _graduation_client(lambda _s, _o: {"graduated": True})
    resp = client.post("/api/v1/strategies/ema/graduate", params={"operator_id": "ankit"})
    assert resp.status_code == 401


def test_graduate_success_is_journaled() -> None:
    handler = lambda slug, operator: {"graduated": True, "reasons": [], "live_cap_pct": "0.01"}  # noqa: E731
    client, journal = _graduation_client(handler)
    resp = client.post(
        "/api/v1/strategies/ema/graduate",
        params={"operator_id": "ankit"},
        headers={"X-Operator-Token": _TOKEN},
    )
    assert resp.status_code == 200
    assert resp.json()["graduated"] is True
    grads = [e for e in journal.entries() if e.kind == "graduation"]
    assert grads and grads[0].payload["operator"] == "ankit"


def test_graduate_ineligible_returns_422_and_is_journaled() -> None:
    handler = lambda slug, operator: {"graduated": False, "reasons": ["OOS Sharpe too low"]}  # noqa: E731
    client, journal = _graduation_client(handler)
    resp = client.post(
        "/api/v1/strategies/weak/graduate",
        params={"operator_id": "ankit"},
        headers={"X-Operator-Token": _TOKEN},
    )
    assert resp.status_code == 422
    assert "OOS Sharpe too low" in resp.json()["detail"]["reasons"]
    # The rejected attempt is still journaled (audit trail).
    assert any(e.kind == "graduation" for e in journal.entries())


def test_graduate_unconfigured_returns_503() -> None:
    client, _, _ = _client()
    resp = client.post(
        "/api/v1/strategies/ema/graduate",
        params={"operator_id": "ankit"},
        headers={"X-Operator-Token": _TOKEN},
    )
    assert resp.status_code == 503


def test_agent_room_returns_pipeline_for_snapshot() -> None:
    kill = KillSwitch()
    journal = Journal()
    snap = "BTC/USDT:2026-01-01T00:00:00+00:00"
    journal.append("analyst_view", {"snapshot_id": snap, "agent": "technical_analyst"})
    journal.append("debate_turn", {"snapshot_id": snap, "agent": "bull_researcher"})
    journal.append("research_verdict", {"snapshot_id": snap, "agent": "research_manager"})
    journal.append("risk_assessment", {"snapshot_id": snap, "agent": "risk_manager"})
    journal.append("decision", {"snapshot_id": snap, "agent": "portfolio_manager"})
    # A record from a different decision must not leak in.
    journal.append("analyst_view", {"snapshot_id": "other", "agent": "technical_analyst"})
    state = ApiState(kill_switch=kill, journal=journal, operator_token=_TOKEN)
    client = TestClient(create_app(state))

    body = client.get(f"/api/v1/decisions/{snap}/agents").json()
    assert body["snapshot_id"] == snap
    kinds = [r["kind"] for r in body["pipeline"]]
    assert kinds == [
        "analyst_view",
        "debate_turn",
        "research_verdict",
        "risk_assessment",
        "decision",
    ]


def test_agent_room_404_for_unknown_snapshot() -> None:
    client, _, _ = _client()
    assert client.get("/api/v1/decisions/nope/agents").status_code == 404


def _postmortem_client() -> TestClient:
    state = ApiState(
        kill_switch=KillSwitch(),
        journal=Journal(),
        operator_token=_TOKEN,
        attribution_provider=lambda tid: (
            {"trade_id": tid, "net_pnl": "20", "signal": "18"} if tid == "t1" else None
        ),
        mistakes_provider=lambda: {"false_signal": {"count": 2, "cost": "40"}},
        improvements_provider=lambda: [{"change_kind": "strategy_weight", "adopted": False}],
        replay_provider=lambda req: {
            "variable": req["variable"],
            "actual_pnl": "100",
            "counterfactual_pnl": "50",
            "delta": "-50",
        },
    )
    return TestClient(create_app(state))


def test_trade_attribution_endpoint() -> None:
    client = _postmortem_client()
    body = client.get("/api/v1/trades/t1/attribution").json()
    assert body["trade_id"] == "t1"
    assert body["signal"] == "18"
    assert client.get("/api/v1/trades/nope/attribution").status_code == 404


def test_mistakes_and_improvements_endpoints() -> None:
    client = _postmortem_client()
    mistakes = client.get("/api/v1/postmortem/mistakes").json()
    assert mistakes["false_signal"]["count"] == 2
    improvements = client.get("/api/v1/postmortem/improvements").json()
    assert improvements[0]["change_kind"] == "strategy_weight"


def test_replay_endpoint_and_unconfigured() -> None:
    client = _postmortem_client()
    body = client.post("/api/v1/postmortem/replay", json={"variable": "size_multiplier"}).json()
    assert body["variable"] == "size_multiplier"
    assert body["delta"] == "-50"

    # No replay provider -> 503.
    bare = TestClient(create_app(ApiState(KillSwitch(), Journal(), _TOKEN)))
    assert bare.post("/api/v1/postmortem/replay", json={"variable": "x"}).status_code == 503
