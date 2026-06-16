"""vix_term_structure_roll — VIX spot-vs-front-month basis trade.

Foundational: Whaley, R. E. (2009). *Understanding VIX*. Journal
of Portfolio Management 35(2), 98-105.
DOI: https://doi.org/10.3905/JPM.2009.35.2.098

Primary methodology: Simon, D. P. & Campasano, J. (2014). *The
VIX Futures Basis: Evidence and Trading Strategies*. Journal of
Derivatives 21(3), 54-69.
DOI: https://doi.org/10.3905/jod.2014.21.3.054
"""

from __future__ import annotations

from alphakit.strategies.options.vix_term_structure_roll.strategy import (
    VIXTermStructureRoll,
)

__all__ = ["VIXTermStructureRoll"]
