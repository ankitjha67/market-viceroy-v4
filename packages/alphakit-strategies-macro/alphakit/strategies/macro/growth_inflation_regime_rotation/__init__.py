"""Growth × inflation 4-cell macro regime rotation (Ilmanen-Maloney-Ross 2014).

Primary methodology (sole anchor): Ilmanen, A., Maloney, T. & Ross, A.
(2014). *Exploring Macroeconomic Sensitivities: How Investments
Respond to Different Economic Environments*. J Portfolio Management
40(3), 87-99. DOI: https://doi.org/10.3905/jpm.2014.40.3.087
"""

from __future__ import annotations

from alphakit.strategies.macro.growth_inflation_regime_rotation.strategy import (
    GrowthInflationRegimeRotation,
)

__all__ = ["GrowthInflationRegimeRotation"]
