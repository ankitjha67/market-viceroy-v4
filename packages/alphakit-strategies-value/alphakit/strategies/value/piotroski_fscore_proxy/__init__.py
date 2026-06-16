"""Piotroski F-Score PROXY (Piotroski 2000).

DOI: 10.2307/2672906

SEVERE DEVIATION: price-based proxy, NOT the real F-Score (ADR-002).
"""

from __future__ import annotations

from alphakit.strategies.value.piotroski_fscore_proxy.strategy import PiotroskiFScoreProxy

__all__ = ["PiotroskiFScoreProxy"]
