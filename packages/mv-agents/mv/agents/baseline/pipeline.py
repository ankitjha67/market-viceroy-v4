"""Deterministic ensemble decision pipeline (Phase-1 baseline).

All MVP crypto strategies run concurrently; this combines their latest signals
into a **governed equal-weight ensemble** and emits an explicit Buy/Sell/Hold
(PRD FR-A5). It is deliberately NOT momentary-best switching (CLAUDE.md #5):
every strategy contributes equally, and grading / governed selection arrive in
Phases 2 and 5. No LLM — the LangGraph agent graph replaces this in Phase 4.

Pure and decoupled from pandas: the loop runs each strategy on the rolling
window and passes the latest per-strategy weight in as a :class:`StrategySignal`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from mv.agents.schemas import TradeDecision

_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class StrategySignal:
    """One strategy's latest signal for an instrument (signed target weight)."""

    strategy: str
    weight: Decimal  # >0 long, <0 short, ~0 flat


def ensemble_decision(
    signals: Sequence[StrategySignal],
    *,
    instrument: str,
    ts: datetime,
    snapshot_id: str,
    hold_threshold: Decimal = Decimal("0.05"),
    risk_ref: str = "pending",
) -> TradeDecision:
    """Combine per-strategy signals into a governed equal-weight Buy/Sell/Hold.

    Args:
        signals: One :class:`StrategySignal` per running strategy (non-empty).
        instrument: The symbol being decided.
        ts: Decision time (UTC).
        snapshot_id: Point-in-time snapshot reference.
        hold_threshold: |ensemble weight| at/below which the call is HOLD.
        risk_ref: Reference to the gating ``RiskAssessment`` (the loop fills
            this after the risk check; defaults to ``"pending"``).

    Returns:
        The proposed :class:`~mv.agents.schemas.TradeDecision`.

    Raises:
        ValueError: If ``signals`` is empty.
    """
    if not signals:
        raise ValueError("ensemble_decision requires at least one strategy signal")

    n = len(signals)
    weights = [s.weight for s in signals]
    ensemble = sum(weights, _ZERO) / n

    longs = sum(1 for w in weights if w > 0)
    shorts = sum(1 for w in weights if w < 0)
    flats = sum(1 for w in weights if abs(w) <= hold_threshold)

    action: Literal["BUY", "SELL", "HOLD"]
    if ensemble > hold_threshold:
        action = "BUY"
        target_size = ensemble
        agree = longs
        opposer = min(signals, key=lambda s: s.weight)  # most negative
        dissent = _dissent(opposer) if opposer.weight < 0 else "none"
    elif ensemble < -hold_threshold:
        action = "SELL"
        target_size = ensemble
        agree = shorts
        opposer = max(signals, key=lambda s: s.weight)  # most positive
        dissent = _dissent(opposer) if opposer.weight > 0 else "none"
    else:
        action = "HOLD"
        target_size = _ZERO
        agree = flats
        opposer = max(signals, key=lambda s: abs(s.weight))  # most directional
        dissent = _dissent(opposer) if abs(opposer.weight) > hold_threshold else "none"

    conviction = agree / n
    rationale = (
        f"ensemble {ensemble:+.4f} over {n} strategies "
        f"({longs} long, {shorts} short, {flats} flat) -> {action}"
    )

    return TradeDecision(
        agent="ensemble_pm",
        instrument=instrument,
        ts=ts,
        snapshot_id=snapshot_id,
        confidence=conviction,
        rationale=rationale,
        action=action,
        target_size=target_size,
        conviction=conviction,
        dissent=dissent,
        risk_ref=risk_ref,
        expected_edge_bps_after_cost=None,
    )


def _dissent(signal: StrategySignal) -> str:
    return f"{signal.strategy} weight {signal.weight:+}"
