"""TIPS vs nominal Treasury rotation on breakeven inflation z-score.

Foundational: Campbell & Shiller (1996), *A Scorecard for Indexed
Government Debt*, NBER Macroeconomics Annual 11, 155–197.
DOI: https://doi.org/10.2307/3585242

Primary methodology: Fleckenstein, Longstaff & Lustig (2014),
*The TIPS-Treasury Bond Puzzle*, Journal of Finance 69(5), 2151–2197.
DOI: https://doi.org/10.1111/jofi.12032
"""

from __future__ import annotations

from alphakit.strategies.rates.breakeven_inflation_rotation.strategy import (
    BreakevenInflationRotation,
)

__all__ = ["BreakevenInflationRotation"]
