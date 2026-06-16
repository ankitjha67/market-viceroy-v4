"""Cross-asset GTAA 12/1 time-series momentum (AMP 2013 §V).

Foundational: Hurst, B., Ooi, Y. H. & Pedersen, L. H. (2017).
*A Century of Evidence on Trend-Following Investing*. Journal of
Portfolio Management 44(1), 15-29.
DOI: https://doi.org/10.3905/jpm.2017.44.1.015

Primary methodology: Asness, C. S., Moskowitz, T. J. & Pedersen, L. H.
(2013). *Value and Momentum Everywhere*. Journal of Finance 68(3),
929-985. §V applies the 12/1 TSMOM rule to a cross-asset universe.
DOI: https://doi.org/10.1111/jofi.12021
"""

from __future__ import annotations

from alphakit.strategies.macro.gtaa_cross_asset_momentum.strategy import (
    GtaaCrossAssetMomentum,
)

__all__ = ["GtaaCrossAssetMomentum"]
