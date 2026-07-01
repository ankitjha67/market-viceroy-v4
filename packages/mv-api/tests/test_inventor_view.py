"""Tests for the Strategy Inventor API rows + endpoints."""

from __future__ import annotations

from typing import Any

from alphakit.bench.inventor import InventionResult, make_candidate
from alphakit.bench.validation.gate import GateResult, GateStatus
from fastapi.testclient import TestClient
from mv.api.app import ApiState, create_app
from mv.api.inventor_view import inventor_rows
from mv.journal.journal import Journal
from mv.risk.kill_switch import KillSwitch

_TOKEN = "operator-secret"


def test_inventor_rows_formats_status_metrics_and_adoptable() -> None:
    a = InventionResult(
        make_candidate("ema_cross", {"fast": 8, "slow": 21}),
        GateResult(
            slug="ema",
            status=GateStatus.ACTIVE,
            data_source="real",
            metrics={"deflated_sharpe": 1.23456},
        ),
    )
    b = InventionResult(
        make_candidate("rsi_reversion", {"period": 2}, family="meanrev"),
        GateResult(slug="rsi", status=GateStatus.OBSERVE, data_source="real", reasons=["thin"]),
    )
    rows = inventor_rows([a, b])
    assert rows[0]["name"] == "ema_cross(fast=8,slow=21)"
    assert rows[0]["status"] == "active" and rows[0]["adoptable"] is True
    assert rows[0]["metrics"]["deflated_sharpe"] == 1.2346  # rounded to 4dp
    assert rows[0]["provenance"] == "param_search"
    assert rows[1]["adoptable"] is False and rows[1]["reasons"] == ["thin"]


def _client(
    candidates: list[dict[str, Any]] | None = None,
    adopt: Any = None,
) -> TestClient:
    state = ApiState(
        kill_switch=KillSwitch(),
        journal=Journal(),
        operator_token=_TOKEN,
        candidates_provider=lambda: candidates or [],
        adopt_candidate_handler=adopt,
    )
    return TestClient(create_app(state))


def test_candidates_endpoint_returns_rows() -> None:
    rows = [{"name": "ema_cross(fast=8,slow=21)", "status": "active", "adoptable": True}]
    resp = _client(candidates=rows).get("/api/v1/candidates")
    assert resp.status_code == 200
    assert resp.json()[0]["name"].startswith("ema_cross")


def test_adopt_requires_operator_token() -> None:
    resp = _client(adopt=lambda _n: {"adopted": True}).post("/api/v1/candidates/ema/adopt")
    assert resp.status_code == 401


def test_adopt_calls_handler_with_token() -> None:
    seen: dict[str, str] = {}

    def adopt(name: str) -> dict[str, Any]:
        seen["name"] = name
        return {"adopted": True, "strategy": name}

    resp = _client(adopt=adopt).post(
        "/api/v1/candidates/ema/adopt", headers={"X-Operator-Token": _TOKEN}
    )
    assert resp.status_code == 200 and resp.json()["adopted"] is True
    assert seen["name"] == "ema"


def test_adopt_503_when_no_handler() -> None:
    resp = _client(adopt=None).post(
        "/api/v1/candidates/ema/adopt", headers={"X-Operator-Token": _TOKEN}
    )
    assert resp.status_code == 503
