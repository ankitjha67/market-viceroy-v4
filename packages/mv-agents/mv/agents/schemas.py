"""Agent I/O schemas (PRD §5) — the typed, journaled contract between stages.

Phase 1 ships the subset the minimal deterministic pipeline needs:
``AgentEnvelope`` (shared base) → ``TradeDecision`` (the executed Buy/Sell/Hold)
→ ``RiskAssessment`` (the inviolable veto) → ``ExecutionResult`` (the fill).
The debate/analyst records (AnalystView, DebateTurn, ResearchVerdict) arrive
with the LangGraph agents in Phase 4.

Records are frozen: they are point-in-time snapshots written to the
tamper-evident journal, never mutated after creation. Money is ``Decimal``
(never float) per the engineering standards.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentEnvelope(BaseModel):
    """Shared envelope every agent/stage output carries (PRD §5)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent: str = Field(min_length=1)
    """Producer id, e.g. ``"ensemble_pm"``, ``"risk_manager"``, ``"execution"``."""

    instrument: str = Field(min_length=1)
    """Instrument symbol the record concerns, e.g. ``"BTC/USDT"``."""

    ts: datetime
    """Decision time (UTC)."""

    snapshot_id: str = Field(min_length=1)
    """Reference to the point-in-time feature snapshot the stage saw."""

    confidence: float = Field(ge=0.0, le=1.0)
    """Producer confidence in this output, in [0, 1]."""

    rationale: str
    """Human-readable justification (audit-grade; never blank in practice)."""

    llm_meta: dict[str, object] | None = None
    """Provider/tokens/latency/cost when an LLM produced this (None otherwise)."""


class TradeDecision(AgentEnvelope):
    """Portfolio-Manager output: the explicit Buy/Sell/Hold (PRD §5, FR-A5)."""

    action: Literal["BUY", "SELL", "HOLD"]
    """The decision. HOLD is a decision too and is journaled like the rest."""

    target_size: Decimal
    """Signed target position size; ``Decimal("0")`` for HOLD."""

    conviction: float = Field(ge=0.0, le=1.0)
    """Conviction in the action, in [0, 1]."""

    dissent: str
    """The strongest opposing view (e.g. the most disagreeing strategy)."""

    risk_ref: str
    """Reference to the ``RiskAssessment`` that gated this decision."""

    expected_edge_bps_after_cost: float | None = None
    """Expected post-cost edge in bps, if estimated."""


class RiskAssessment(AgentEnvelope):
    """Risk-Manager output: the inviolable pre-trade verdict (PRD §5, FR-R1)."""

    approved: bool
    """True only if no hard limit is breached."""

    breached_limits: list[str] = Field(default_factory=list)
    """Names of limits breached (empty when approved)."""

    max_size_allowed: Decimal
    """The largest size the risk engine permits for this instrument now."""

    notes: str = ""
    """Optional detail on the assessment."""


class ExecutionResult(AgentEnvelope):
    """Execution-Agent output: the (paper) fill outcome (PRD §5, FR-X)."""

    order_type: Literal["market", "limit", "post_only"]
    """Order type the execution agent selected."""

    intended_price: Decimal | None = None
    """Reference/intended price at submission (None for pure market intent)."""

    fill_price: Decimal | None = None
    """Actual fill price (None if not filled)."""

    slippage_bps: float
    """Realized slippage in bps vs the intended/reference price."""

    fees: Decimal
    """Total fees paid on the fill (Decimal)."""

    status: Literal["filled", "partial", "rejected", "cancelled"]
    """Terminal status of the order."""


__all__ = [
    "AgentEnvelope",
    "ExecutionResult",
    "RiskAssessment",
    "TradeDecision",
]
