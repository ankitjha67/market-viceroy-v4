"""The agent input context + shared stance/score helpers (PRD §4.5, FR-A2).

Every roster agent reasons over an :class:`AgentContext` — the point-in-time
evidence the desk saw at one decision time: the as-of feature snapshot (Phase-3
``asof_join`` output, keyed by feature name) plus the Phase-1 strategy ensemble
the Technical analyst reuses. Agents read **only** this context, so the whole
pipeline is point-in-time by construction (no look-ahead) and deterministic.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from mv.agents.baseline.pipeline import StrategySignal

Stance = Literal["bullish", "neutral", "bearish"]


@dataclass(frozen=True)
class AgentContext:
    """The point-in-time evidence one agent decision is built from."""

    instrument: str
    """The symbol being decided, e.g. ``"BTC/USDT"``."""

    ts: datetime
    """Decision time (UTC)."""

    snapshot_id: str
    """Shared id linking every record of this decision to its feature snapshot."""

    features: Mapping[str, float] = field(default_factory=dict)
    """As-of point-in-time features keyed by name (e.g. ``"sentiment"``,
    ``"regime"``, ``"momentum"``). A missing key means no coverage — the agent
    degrades to neutral/low-confidence rather than fabricating a view."""

    signals: Sequence[StrategySignal] = ()
    """The Phase-1 strategy ensemble's latest signed weights (the Technical
    analyst's evidence). Empty for assets with no wired strategies."""


def clip_unit(value: float) -> float:
    """Clamp a score into the ``[-1, 1]`` directional range."""
    return max(-1.0, min(1.0, value))


def stance_from_score(score: float, *, neutral_band: float = 0.1) -> Stance:
    """Map a directional score to a stance, with a dead-band around zero."""
    if score > neutral_band:
        return "bullish"
    if score < -neutral_band:
        return "bearish"
    return "neutral"


def confidence_from_score(score: float) -> float:
    """Confidence = magnitude of conviction, in ``[0, 1]``."""
    return min(1.0, abs(score))
