"""Unit tests for the agent I/O schemas (PRD §5)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TypedDict

import pytest
from mv.agents.schemas import (
    AgentEnvelope,
    ExecutionResult,
    RiskAssessment,
    TradeDecision,
)
from pydantic import ValidationError

_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _EnvKw(TypedDict):
    agent: str
    instrument: str
    ts: datetime
    snapshot_id: str
    confidence: float
    rationale: str


def _envelope_kwargs(agent: str = "ensemble_pm") -> _EnvKw:
    return {
        "agent": agent,
        "instrument": "BTC/USDT",
        "ts": _TS,
        "snapshot_id": "snap-1",
        "confidence": 0.7,
        "rationale": "ensemble net long",
    }


def test_trade_decision_roundtrip() -> None:
    d = TradeDecision(
        **_envelope_kwargs(),
        action="BUY",
        target_size=Decimal("0.5"),
        conviction=0.8,
        dissent="rsi_reversion_2 says overbought",
        risk_ref="risk-1",
        expected_edge_bps_after_cost=12.5,
    )
    assert d.action == "BUY"
    assert d.target_size == Decimal("0.5")
    # Decimal survives JSON round-trip without float corruption.
    restored = TradeDecision.model_validate_json(d.model_dump_json())
    assert restored == d
    assert isinstance(restored.target_size, Decimal)


def test_hold_has_zero_size() -> None:
    d = TradeDecision(
        **_envelope_kwargs(),
        action="HOLD",
        target_size=Decimal("0"),
        conviction=0.1,
        dissent="",
        risk_ref="risk-1",
    )
    assert d.action == "HOLD"
    assert d.target_size == Decimal("0")


def test_confidence_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        AgentEnvelope(
            agent="x",
            instrument="BTC/USDT",
            ts=_TS,
            snapshot_id="snap-1",
            confidence=1.5,
            rationale="r",
        )


def test_records_are_frozen() -> None:
    env = AgentEnvelope(**_envelope_kwargs())
    with pytest.raises(ValidationError):
        env.confidence = 0.2


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        AgentEnvelope(**_envelope_kwargs(), bogus="x")  # type: ignore[call-arg]


def test_risk_assessment_defaults() -> None:
    r = RiskAssessment(
        **_envelope_kwargs(),
        approved=True,
        max_size_allowed=Decimal("1.0"),
    )
    assert r.approved is True
    assert r.breached_limits == []
    assert r.notes == ""


def test_risk_assessment_breach() -> None:
    r = RiskAssessment(
        **_envelope_kwargs(agent="risk_manager"),
        approved=False,
        breached_limits=["max_position", "daily_loss"],
        max_size_allowed=Decimal("0"),
        notes="daily loss limit hit",
    )
    assert r.approved is False
    assert "daily_loss" in r.breached_limits


def test_execution_result() -> None:
    e = ExecutionResult(
        **_envelope_kwargs(agent="execution"),
        order_type="market",
        intended_price=Decimal("42000.0"),
        fill_price=Decimal("42010.5"),
        slippage_bps=2.5,
        fees=Decimal("0.42"),
        status="filled",
    )
    assert e.status == "filled"
    assert isinstance(e.fees, Decimal)
    assert e.fill_price == Decimal("42010.5")
