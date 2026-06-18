"""Agent I/O schemas (PRD §5) — the typed, journaled contract between stages.

The full pipeline contract (PRD §5):
``[AnalystView]* → [DebateTurn]* → ResearchVerdict → RiskAssessment →
TradeDecision → ExecutionResult``, all sharing one ``snapshot_id`` so the whole
decision is reconstructable from the journal. ``AgentEnvelope`` is the shared
base every record carries. Phase 1 shipped the executed subset (TradeDecision /
RiskAssessment / ExecutionResult); Phase 4 adds the research records the
LangGraph agents produce: ``AnalystView`` (each analyst's stance/score),
``DebateTurn`` (a bull/bear claim), and ``ResearchVerdict`` (the Research
Manager's adjudicated thesis).

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


class AnalystView(AgentEnvelope):
    """An analyst's directional read on an instrument (PRD §5, FR-A2)."""

    stance: Literal["bullish", "neutral", "bearish"]
    """The analyst's qualitative call."""

    score: float = Field(ge=-1.0, le=1.0)
    """Directional score in [-1, 1] (negative bearish, positive bullish)."""

    horizon: Literal["intraday", "swing", "position"]
    """The horizon the view applies to."""

    key_factors: list[str] = Field(default_factory=list)
    """The salient evidence the view rests on (point-in-time feature names)."""


class DebateTurn(AgentEnvelope):
    """One bull/bear claim in the research debate (PRD §5, FR-A4)."""

    side: Literal["bull", "bear"]
    """Which side of the debate this turn argues."""

    claim: str
    """The argument advanced this turn."""

    evidence_refs: list[str] = Field(default_factory=list)
    """References to the evidence (analyst views / feature names) cited."""


class ResearchVerdict(AgentEnvelope):
    """Research-Manager adjudication of the debate (PRD §5, FR-A4)."""

    thesis: str
    """The synthesized thesis the desk will act on."""

    net_stance: Literal["bullish", "neutral", "bearish"]
    """The adjudicated net stance after weighing bull vs bear."""

    bull_strength: float = Field(ge=0.0, le=1.0)
    """Aggregate strength of the bull case, in [0, 1]."""

    bear_strength: float = Field(ge=0.0, le=1.0)
    """Aggregate strength of the bear case, in [0, 1]."""


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
    "AnalystView",
    "DebateTurn",
    "ExecutionResult",
    "ResearchVerdict",
    "RiskAssessment",
    "TradeDecision",
]
