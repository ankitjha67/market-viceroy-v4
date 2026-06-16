"""iron_condor_monthly — 4-leg defined-risk short-volatility monthly write.

Foundational: Hill, J. M., Balasubramanian, V., Gregory, K. &
Tierens, I. (2006). *Finding alpha via covered index writing*.
Journal of Derivatives, 13(3), 51-65.
DOI: https://doi.org/10.3905/jod.2006.622777

Primary methodology: CBOE CNDR (Iron Condor Index) construction
methodology document (CBOE Global Markets, 2010s onward).
"""

from __future__ import annotations

from alphakit.strategies.options.iron_condor_monthly.strategy import IronCondorMonthly

__all__ = ["IronCondorMonthly"]
