"""Calendar-based seasonal trade on US grain futures.

Foundational: Fama, E. F. & French, K. R. (1987), *Commodity Futures
Prices: Some Evidence on Forecast Power, Premiums, and the Theory
of Storage*, Journal of Business 60(1), 55–73. Documents the
storage-cost / seasonality dynamics in commodity-futures returns.
DOI: https://doi.org/10.1086/296385

Primary methodology: Sørensen, C. (2002), *Modeling Seasonality in
Agricultural Commodity Futures*, Journal of Futures Markets 22(5),
393–426. Documents calendar-based seasonality in corn, soybeans,
and wheat: prices tend to peak in late spring (planting-
uncertainty premium) and trough at harvest (Sep-Oct for
corn/soybeans, Jul-Aug for winter wheat).
DOI: https://doi.org/10.1002/fut.10017
"""

from __future__ import annotations

from alphakit.strategies.commodity.grain_seasonality.strategy import GrainSeasonality

__all__ = ["GrainSeasonality"]
