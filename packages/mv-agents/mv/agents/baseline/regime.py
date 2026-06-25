"""Point-in-time market-regime detection for regime-adaptive ensemble weighting.

The ensemble's family weights are driven by **market structure** — how trending
vs ranging recent price action is — never by strategy PnL. Performance-chasing
(weighting whoever made money lately) is the naive behaviour CLAUDE.md #5
forbids; governed weight changes stay the Phase-5 propose-only, human-gated path.

Kaufman's Efficiency Ratio measures trendiness in ``[0, 1]``: ``~1`` when price
moves in a straight line, ``~0`` when it zig-zags. Trend followers are upweighted
in trends, mean-reversion in chop. Deterministic and bounded; the overlapping
lookback smooths it bar-to-bar (anti-whipsaw), and a weight ``floor`` keeps both
families always in play so the ensemble never degenerates to a single bet.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegimeView:
    """The detected regime and the family weights it implies (a glass-box record).

    ``trend_score`` is Kaufman's Efficiency Ratio in ``[0, 1]``; ``trend_weight``
    and ``meanrev_weight`` are the family weights the ensemble applies (they sum
    to 1 by construction).
    """

    trend_score: float
    label: str  # "trending" | "transitional" | "ranging"
    trend_weight: float
    meanrev_weight: float


def efficiency_ratio(closes: Sequence[float], lookback: int) -> float:
    """Kaufman's Efficiency Ratio over the last ``lookback`` closes, in ``[0, 1]``.

    ``|net move| / Σ|bar-to-bar move|`` — 1.0 for a perfectly straight move,
    toward 0 as the path zig-zags. Returns 0.0 for a flat or too-short series.
    """
    n = len(closes)
    if n < 2 or lookback < 1:
        return 0.0
    span = min(lookback, n - 1)
    window = closes[-(span + 1) :]
    net = abs(window[-1] - window[0])
    path = sum(abs(window[i] - window[i - 1]) for i in range(1, len(window)))
    if path <= 0.0:
        return 0.0
    return max(0.0, min(1.0, net / path))


def detect_regime(
    closes: Sequence[float],
    *,
    lookback: int = 30,
    floor: float = 0.1,
) -> RegimeView:
    """Detect the trend/range regime and the family weights it implies.

    ``floor`` (clamped to ``[0, 0.49]``) is the minimum weight each family keeps,
    so neither trend nor mean-reversion is ever switched fully off (diversification
    + anti-whipsaw). ``trend_weight + meanrev_weight == 1`` by construction.
    """
    score = efficiency_ratio(closes, lookback)
    floor = max(0.0, min(floor, 0.49))
    span = 1.0 - 2.0 * floor
    trend_weight = floor + span * score
    meanrev_weight = floor + span * (1.0 - score)
    if score >= 0.6:
        label = "trending"
    elif score <= 0.35:
        label = "ranging"
    else:
        label = "transitional"
    return RegimeView(
        trend_score=score,
        label=label,
        trend_weight=trend_weight,
        meanrev_weight=meanrev_weight,
    )


def family_weight(category: str, regime: RegimeView) -> float:
    """The ensemble weight for a strategy in ``category`` (``"trend" | "meanrev"``)."""
    return regime.meanrev_weight if category == "meanrev" else regime.trend_weight


__all__ = ["RegimeView", "detect_regime", "efficiency_ratio", "family_weight"]
