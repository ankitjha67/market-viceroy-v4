"""Regime-conditioned criterion (PRD FR-V2).

Wraps the existing volatility-based regime split
(:func:`alphakit.bench.metrics.regime_performance`, bull/bear/sideways Sharpe)
into a gate criterion: a credible strategy must not collapse in any regime. The
HMM/Markov regime classifier (FR-S6) is a Phase-5 upgrade.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from alphakit.bench.metrics import regime_performance


@dataclass(frozen=True, slots=True)
class RegimeResult:
    """Per-regime Sharpe plus the worst-regime pass/fail."""

    per_regime: dict[str, float]
    worst_sharpe: float
    passed: bool


def regime_consistency(returns: pd.Series, *, floor: float = -0.5) -> RegimeResult:
    """Pass if no regime's Sharpe falls below ``floor``."""
    per_regime = regime_performance(returns)
    worst = min(per_regime.values()) if per_regime else 0.0
    return RegimeResult(per_regime=per_regime, worst_sharpe=worst, passed=worst >= floor)
