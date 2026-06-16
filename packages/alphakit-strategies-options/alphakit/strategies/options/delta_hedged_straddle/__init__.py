"""delta_hedged_straddle — long ATM straddle with daily delta hedge.

Foundational: Black, F. & Scholes, M. (1973),
*The Pricing of Options and Corporate Liabilities*, Journal of
Political Economy 81(3), 637-654.
DOI: https://doi.org/10.1086/260062

Primary methodology: Carr, P. & Wu, L. (2009),
*Variance Risk Premia*, Review of Financial Studies 22(3), 1311-1341.
DOI: https://doi.org/10.1093/rfs/hhn038
"""

from __future__ import annotations

from alphakit.strategies.options.delta_hedged_straddle.strategy import (
    DeltaHedgedStraddle,
)

__all__ = ["DeltaHedgedStraddle"]
