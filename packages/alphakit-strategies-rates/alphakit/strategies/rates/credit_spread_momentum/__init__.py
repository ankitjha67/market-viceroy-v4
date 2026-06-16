"""Single-asset 6/0 momentum on investment-grade corporate bond returns.

Primary methodology: Jostova, Nikolova, Philipov & Stahel (2013),
*Momentum in Corporate Bond Returns*, Review of Financial Studies
26(7), 1649–1693.
DOI: https://doi.org/10.1093/rfs/hht022
"""

from __future__ import annotations

from alphakit.strategies.rates.credit_spread_momentum.strategy import CreditSpreadMomentum

__all__ = ["CreditSpreadMomentum"]
