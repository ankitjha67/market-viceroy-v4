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
