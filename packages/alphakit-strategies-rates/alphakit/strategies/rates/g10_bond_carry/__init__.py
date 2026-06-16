"""G10 cross-country sovereign bond carry — long-short cross-sectional rank.

Primary methodology: Asness, Moskowitz & Pedersen (2013) §V,
*Value and Momentum Everywhere*, Journal of Finance 68(3), 929–985.
DOI: https://doi.org/10.1111/jofi.12021
"""

from __future__ import annotations

from alphakit.strategies.rates.g10_bond_carry.strategy import G10BondCarry

__all__ = ["G10BondCarry"]
