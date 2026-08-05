"""Market-intel aggregation: sources -> agent features -> deck payload.

The end-to-end wire for the Phase-14 sources: the serve loop refreshes Fear &
Greed, perp funding, and (when credentialed) Reddit social sentiment on a news
cadence, then this module turns those readings plus the news lexicon into the
exact feature names the analyst roster consumes (``news_sentiment``,
``sentiment``, ``flow``, ``regime``). Coverage discipline throughout: a missing
reading yields an ABSENT key, never a fabricated neutral, so uncovered
analysts keep degrading honestly. Pure and unit-tested.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

from mv.failover.adapters.funding_feed import FundingRate, funding_flow_score
from mv.intelligence.sources.fear_greed import FearGreed, fear_greed_score


def signed_efficiency(closes: list[float], *, lookback: int = 30) -> float | None:
    """Directional Kaufman efficiency in [-1, 1]: signed net move / path length.

    Positive = an efficient up-move, negative = an efficient down-move, near
    zero = chop. ``None`` when there is not enough history (no coverage).
    """
    if len(closes) < max(3, lookback):
        return None
    window = closes[-lookback:]
    path = sum(abs(b - a) for a, b in pairwise(window))
    if path <= 0:
        return 0.0
    return max(-1.0, min(1.0, (window[-1] - window[0]) / path))


def features_for(
    symbol: str,
    *,
    news_sentiment: dict[str, float],
    fear_greed: FearGreed | None,
    funding: dict[str, FundingRate],
    social: dict[str, float],
    regime_direction: float | None,
) -> dict[str, float]:
    """The analyst feature map for one symbol (absent key = no coverage).

    ``sentiment`` blends the market-wide mood readings that exist (Fear & Greed
    and the social aggregate) with equal weight; per-instrument news keeps its
    own ``news_sentiment`` channel; ``flow`` is the crowd-positioning score from
    the symbol's own funding rate; ``regime`` is the signed efficiency of the
    symbol's recent path.
    """
    features: dict[str, float] = {}
    news = news_sentiment.get(symbol)
    if news is not None:
        features["news_sentiment"] = max(-1.0, min(1.0, float(news)))
    mood: list[float] = []
    if fear_greed is not None:
        mood.append(fear_greed_score(fear_greed.value))
    if social:
        mood.append(max(-1.0, min(1.0, sum(social.values()) / len(social))))
    if mood:
        features["sentiment"] = sum(mood) / len(mood)
    rate = funding.get(symbol)
    if rate is not None:
        features["flow"] = funding_flow_score(rate.rate)
    if regime_direction is not None:
        features["regime"] = max(-1.0, min(1.0, regime_direction))
    return features


def intel_payload(
    *,
    fear_greed: FearGreed | None,
    funding: dict[str, FundingRate],
    social: dict[str, float],
) -> dict[str, Any]:
    """The ``GET /api/v1/intel`` shape (JSON-safe, floats only)."""
    return {
        "fear_greed": (
            {
                "value": fear_greed.value,
                "label": fear_greed.label,
                "score": round(fear_greed_score(fear_greed.value), 3),
            }
            if fear_greed is not None
            else None
        ),
        "funding": {
            sym: {"rate": rate.rate, "open_interest": rate.open_interest}
            for sym, rate in sorted(funding.items())
        },
        "social": {name: round(score, 3) for name, score in sorted(social.items())},
    }


__all__ = ["features_for", "intel_payload", "signed_efficiency"]
