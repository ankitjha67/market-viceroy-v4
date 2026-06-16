"""short_strangle_monthly — 2-leg short-volatility monthly write.

Foundational: Coval, J. D. & Shumway, T. (2001),
*Expected option returns*, Journal of Finance 56(3), 983-1009.
DOI: https://doi.org/10.1111/0022-1082.00352

Primary methodology: Bondarenko, O. (2014),
*Why Are Put Options So Expensive?*, Quarterly Journal of Finance
4(1), 1450015.
DOI: https://doi.org/10.1142/S2010139214500050
"""

from __future__ import annotations

from alphakit.strategies.options.short_strangle_monthly.strategy import (
    ShortStrangleMonthly,
)

__all__ = ["ShortStrangleMonthly"]
