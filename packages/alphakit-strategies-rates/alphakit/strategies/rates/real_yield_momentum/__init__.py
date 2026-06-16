"""12/1 time-series momentum on TIPS real-yield-derived bond returns.

Foundational: Pflueger & Viceira (2011), *An Empirical Decomposition
of Risk and Liquidity Premia in Government Bonds*, NBER WP 16892.
DOI: https://doi.org/10.3386/w16892

Primary methodology: Asness, Moskowitz & Pedersen (2013) §V, *Value
and Momentum Everywhere*, Journal of Finance 68(3), 929–985.
DOI: https://doi.org/10.1111/jofi.12021
"""

from __future__ import annotations

from alphakit.strategies.rates.real_yield_momentum.strategy import RealYieldMomentum

__all__ = ["RealYieldMomentum"]
