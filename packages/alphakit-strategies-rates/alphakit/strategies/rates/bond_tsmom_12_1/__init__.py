"""Time-series momentum on 10Y treasury returns, 12/1.

Foundational: Moskowitz, Ooi & Pedersen (2012),
*Time Series Momentum*, Journal of Financial Economics 104(2), 228–250.
DOI: https://doi.org/10.1016/j.jfineco.2011.11.003

Primary methodology: Asness, Moskowitz & Pedersen (2013),
*Value and Momentum Everywhere*, Journal of Finance 68(3), 929–985 (§V).
DOI: https://doi.org/10.1111/jofi.12021
"""

from __future__ import annotations

from alphakit.strategies.rates.bond_tsmom_12_1.strategy import BondTSMOM12m1m

__all__ = ["BondTSMOM12m1m"]
