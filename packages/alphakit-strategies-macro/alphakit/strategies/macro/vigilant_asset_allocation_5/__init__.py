"""Vigilant Asset Allocation on 5 ETFs (Keller-Keuning 2017 VAA, G4 variant).

Foundational: Keller, W. J. & Keuning, J. W. (2014).
*A Century of Generalized Momentum: From Flexible Asset Allocations
(FAA) to Elastic Asset Allocation (EAA)*. SSRN 2543979.
DOI: https://doi.org/10.2139/ssrn.2543979

Primary methodology: Keller, W. J. & Keuning, J. W. (2017).
*Breadth Momentum and the Canary Universe: Defensive Asset
Allocation (DAA)*. SSRN 3002624.
DOI: https://doi.org/10.2139/ssrn.3002624
"""

from __future__ import annotations

from alphakit.strategies.macro.vigilant_asset_allocation_5.strategy import (
    VigilantAssetAllocation5,
)

__all__ = ["VigilantAssetAllocation5"]
