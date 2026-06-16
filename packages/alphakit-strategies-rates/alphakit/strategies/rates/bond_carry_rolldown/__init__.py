"""Single-asset bond carry-and-rolldown duration positioning.

Foundational: Fama (1984), *Forward Rates as Predictors of Future
Spot Rates*, Journal of Financial Economics 13(4), 509–528.
DOI: https://doi.org/10.1016/0304-405X(84)90013-8

Primary methodology: Koijen, Moskowitz, Pedersen & Vrugt (2018),
*Carry*, Journal of Financial Economics 127(2), 197–225.
DOI: https://doi.org/10.1016/j.jfineco.2017.11.002
"""

from __future__ import annotations

from alphakit.strategies.rates.bond_carry_rolldown.strategy import BondCarryRolldown

__all__ = ["BondCarryRolldown"]
