"""Cross-sectional mean-reversion on PCA residuals after top-3 yield-curve factors.

Foundational + primary methodology: Litterman & Scheinkman (1991),
*Common Factors Affecting Bond Returns*, Journal of Fixed Income 1(1).
DOI: https://doi.org/10.3905/jfi.1991.692347
"""

from __future__ import annotations

from alphakit.strategies.rates.yield_curve_pca_trade.strategy import YieldCurvePCATrade

__all__ = ["YieldCurvePCATrade"]
