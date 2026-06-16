"""Cross-commodity 12/1 time-series momentum.

Foundational: Moskowitz, Ooi & Pedersen (2012),
*Time Series Momentum*, Journal of Financial Economics 104(2), 228–250.
DOI: https://doi.org/10.1016/j.jfineco.2011.11.003

Primary methodology: Asness, Moskowitz & Pedersen (2013) §V,
*Value and Momentum Everywhere*, Journal of Finance 68(3), 929–985.
DOI: https://doi.org/10.1111/jofi.12021
"""

from __future__ import annotations

from alphakit.strategies.commodity.commodity_tsmom.strategy import CommodityTSMOM12m1m

__all__ = ["CommodityTSMOM12m1m"]
