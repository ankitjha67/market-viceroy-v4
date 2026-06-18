"""Research Pod + Analyst Pod — deterministic analysts producing AnalystViews.

Roster (PRD FR-A2): Research Pod = News, Macro, Flow; Analyst Pod =
Fundamentals, Valuation, Technical, Sentiment. Each reads the point-in-time
:class:`~mv.agents.roster.context.AgentContext` and emits one
:class:`~mv.agents.schemas.AnalystView`. The Technical analyst reuses the
Phase-1 strategy ensemble (`StrategySignal` weights); the others read a single
as-of feature. **When a feature is absent (e.g. no fundamentals for a crypto
pair) the analyst returns a neutral, zero-confidence view with an honest
rationale — never a fabricated stance.** Deterministic by construction.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean
from typing import Literal

from mv.agents.roster.context import (
    AgentContext,
    clip_unit,
    confidence_from_score,
    stance_from_score,
)
from mv.agents.schemas import AnalystView

Horizon = Literal["intraday", "swing", "position"]


@dataclass(frozen=True, slots=True)
class _FeatureSpec:
    """A single-feature analyst: which feature it reads and on what horizon."""

    agent: str
    feature: str
    horizon: Horizon
    neutral_band: float = 0.1


# The single-feature analysts (the Technical analyst is special — see below).
# Each `feature` is expected as a directional value in roughly [-1, 1]
# (bullish positive). Producers stamp these as point-in-time features.
_FEATURE_ANALYSTS: tuple[_FeatureSpec, ...] = (
    _FeatureSpec("news_analyst", "news_sentiment", "intraday"),
    _FeatureSpec("macro_analyst", "regime", "position"),
    _FeatureSpec("flow_analyst", "flow", "intraday"),
    _FeatureSpec("fundamentals_analyst", "fundamental_score", "position"),
    _FeatureSpec("valuation_analyst", "valuation_score", "position"),
    _FeatureSpec("sentiment_analyst", "sentiment", "swing"),
)


def _view(
    spec: _FeatureSpec, ctx: AgentContext, *, score: float, factors: list[str], rationale: str
) -> AnalystView:
    return AnalystView(
        agent=spec.agent,
        instrument=ctx.instrument,
        ts=ctx.ts,
        snapshot_id=ctx.snapshot_id,
        confidence=confidence_from_score(score),
        rationale=rationale,
        stance=stance_from_score(score, neutral_band=spec.neutral_band),
        score=score,
        horizon=spec.horizon,
        key_factors=factors,
    )


def feature_analyst(spec: _FeatureSpec, ctx: AgentContext) -> AnalystView:
    """One single-feature analyst's view, degrading to neutral if uncovered."""
    raw = ctx.features.get(spec.feature)
    if raw is None:
        return _view(
            spec,
            ctx,
            score=0.0,
            factors=[],
            rationale=f"no {spec.feature} coverage for {ctx.instrument}; neutral",
        )
    score = clip_unit(raw)
    stance = stance_from_score(score, neutral_band=spec.neutral_band)
    return _view(
        spec,
        ctx,
        score=score,
        factors=[spec.feature],
        rationale=f"{spec.feature}={raw:+.3f} -> {stance}",
    )


def technical_analyst(ctx: AgentContext) -> AnalystView:
    """Technical view from the Phase-1 strategy ensemble (or momentum fallback)."""
    spec = _FeatureSpec("technical_analyst", "momentum", "swing")
    if ctx.signals:
        weights = [float(s.weight) for s in ctx.signals]
        score = clip_unit(fmean(weights))
        factors = [s.strategy for s in ctx.signals]
        longs = sum(1 for w in weights if w > 0)
        shorts = sum(1 for w in weights if w < 0)
        rationale = (
            f"ensemble of {len(weights)} strategies ({longs} long, {shorts} short) -> {score:+.3f}"
        )
        return _view(spec, ctx, score=score, factors=factors, rationale=rationale)
    return feature_analyst(spec, ctx)


def run_analysts(ctx: AgentContext) -> list[AnalystView]:
    """All seven analysts' views over one context (deterministic order)."""
    views: list[AnalystView] = [feature_analyst(spec, ctx) for spec in _FEATURE_ANALYSTS]
    views.append(technical_analyst(ctx))
    return views


def analyst_agents() -> Sequence[str]:
    """The roster's analyst agent ids (for routing / display)."""
    return (*(spec.agent for spec in _FEATURE_ANALYSTS), "technical_analyst")
