"""WTI-Brent crude-oil pairs-trading spread.

Foundational: Gatev, E., Goetzmann, W. N. & Rouwenhorst, K. G.
(2006), *Pairs Trading: Performance of a Relative-Value Arbitrage
Rule*, Review of Financial Studies 19(3), 797–827. Foundational
methodology for pairs-trading.
DOI: https://doi.org/10.1093/rfs/hhj020

Primary methodology: Reboredo, J. C. (2011), *How do crude oil
prices co-move? A copula approach*, Energy Economics 33(5),
948–955. Documents the WTI-Brent cointegration and the conditions
for transient divergence.
DOI: https://doi.org/10.1016/j.eneco.2011.04.006
"""

from __future__ import annotations

from alphakit.strategies.commodity.wti_brent_spread.strategy import WTIBrentSpread

__all__ = ["WTIBrentSpread"]
