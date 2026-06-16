"""2s5s10s curve butterfly — mean-reversion on the third PC of the curve.

Foundational + primary methodology: Litterman & Scheinkman (1991),
*Common Factors Affecting Bond Returns*, Journal of Fixed Income 1(1).
DOI: https://doi.org/10.3905/jfi.1991.692347
"""

from __future__ import annotations

from alphakit.strategies.rates.curve_butterfly_2s5s10s.strategy import CurveButterfly2s5s10s

__all__ = ["CurveButterfly2s5s10s"]
