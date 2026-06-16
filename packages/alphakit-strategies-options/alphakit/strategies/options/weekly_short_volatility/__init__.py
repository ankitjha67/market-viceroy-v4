"""weekly_short_volatility — 2-leg weekly OTM put+call write (reframed weekly_theta_harvest).

Foundational: Carr, P. & Wu, L. (2009),
*Variance Risk Premia*, Review of Financial Studies 22(3), 1311-1341.
DOI: https://doi.org/10.1093/rfs/hhn038

Primary methodology: Bondarenko, O. (2014),
*Why Are Put Options So Expensive?*, Quarterly Journal of Finance
4(1), 1450015.
DOI: https://doi.org/10.1142/S2010139214500050
"""

from __future__ import annotations

from alphakit.strategies.options.weekly_short_volatility.strategy import (
    WeeklyShortVolatility,
)

__all__ = ["WeeklyShortVolatility"]
