"""Cross-sectional curve-carry on a commodity-futures panel (KMPV 2018 §IV).

Foundational: Erb, C. B. & Harvey, C. R. (2006), *The Strategic and
Tactical Value of Commodity Futures*, Financial Analysts Journal
62(2), 69–97. Section III formalises the single-asset curve-carry
rule.
DOI: https://doi.org/10.2469/faj.v62.n2.4084

Primary methodology: Koijen, R. S. J., Moskowitz, T. J., Pedersen,
L. H. & Vrugt, E. B. (2018), *Carry*, Journal of Financial Economics
127(2), 197–225. Section IV applies the unified carry framework to
the commodity-futures panel and documents a long-short carry book
that ranks across the cross-section.
DOI: https://doi.org/10.1016/j.jfineco.2017.11.002
"""

from __future__ import annotations

from alphakit.strategies.commodity.commodity_curve_carry.strategy import (
    CommodityCurveCarry,
)

__all__ = ["CommodityCurveCarry"]
