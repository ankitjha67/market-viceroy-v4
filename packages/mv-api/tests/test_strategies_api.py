"""Tests for the Strategy Lab read API (reads the real catalog, no network)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from mv.api.app import ApiState, create_app
from mv.journal.journal import Journal
from mv.risk.kill_switch import KillSwitch


def _client() -> TestClient:
    state = ApiState(kill_switch=KillSwitch(), journal=Journal(), operator_token="t")
    return TestClient(create_app(state))


def test_list_strategies() -> None:
    rows = _client().get("/api/v1/strategies").json()
    # The full catalog (109 strategies) is surfaced.
    assert len(rows) >= 100
    slugs = {r["slug"] for r in rows}
    assert {"ema_cross_12_26", "bond_carry_rolldown"} <= slugs
    sample = next(r for r in rows if r["slug"] == "ema_cross_12_26")
    assert sample["family"] == "trend"
    assert sample["gate_status"] in {"active", "observe", "failed"}
    assert "data_source" in sample


def test_get_strategy_detail() -> None:
    body = _client().get("/api/v1/strategies/bond_carry_rolldown").json()
    assert body["slug"] == "bond_carry_rolldown"
    assert body["family"] == "rates"
    assert "results" in body


def test_unknown_strategy_404() -> None:
    resp = _client().get("/api/v1/strategies/does_not_exist")
    assert resp.status_code == 404


def test_real_feed_strategy_shows_provenance() -> None:
    # A real-feed strategy reports its real data_source from benchmark_results.json.
    body = _client().get("/api/v1/strategies/bond_carry_rolldown").json()
    assert "real" in body["data_source"]
