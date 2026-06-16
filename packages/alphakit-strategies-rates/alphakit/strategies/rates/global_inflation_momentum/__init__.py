"""Cross-country inflation-momentum-driven bond tilt.

Foundational: Ilmanen, A. (2011). *Expected Returns: An Investor's
Guide to Harvesting Market Rewards*, Wiley. Ch 12.

Primary methodology: Ilmanen, Maloney & Ross (2014), *Exploring
Macroeconomic Sensitivities*, Journal of Portfolio Management 40(3),
87–99.
DOI: https://doi.org/10.3905/jpm.2014.40.3.087
"""

from __future__ import annotations

from alphakit.strategies.rates.global_inflation_momentum.strategy import (
    GlobalInflationMomentum,
)

__all__ = ["GlobalInflationMomentum"]
