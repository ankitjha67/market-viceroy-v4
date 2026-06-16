"""Altman Z-Score PROXY (Altman 1968).

DOI: 10.1111/j.1540-6261.1968.tb00843.x

SEVERE DEVIATION: price-based proxy, NOT the real Z-Score (ADR-002).
"""

from __future__ import annotations

from alphakit.strategies.value.altman_zscore_proxy.strategy import AltmanZScoreProxy

__all__ = ["AltmanZScoreProxy"]
