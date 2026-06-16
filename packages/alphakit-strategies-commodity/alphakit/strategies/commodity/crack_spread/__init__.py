"""3-2-1 crack-spread mean-reversion trade.

Foundational: Geman, H. (2005), *Commodities and Commodity
Derivatives: Modeling and Pricing for Agriculturals, Metals and
Energy*, Wiley. Textbook treatment of the energy-product spread
trades and the 3-2-1 refining-margin convention.

Primary methodology: Girma, P. B. & Paulson, A. S. (1999), *Risk
Arbitrage Opportunities in Petroleum Futures Spreads*, Journal of
Futures Markets 19(8), 931–955. Documents the crack spread as a
mean-reverting risk-arbitrage trade between crude oil (CL) and
refined products (RB gasoline + HO heating oil).
DOI: https://doi.org/10.1002/(SICI)1096-9934(199912)19:8<931::AID-FUT5>3.0.CO;2-L
"""

from __future__ import annotations

from alphakit.strategies.commodity.crack_spread.strategy import CrackSpread

__all__ = ["CrackSpread"]
