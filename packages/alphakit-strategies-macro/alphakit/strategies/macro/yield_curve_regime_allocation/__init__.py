"""Yield-curve-slope 3-cell regime allocation (Estrella-Hardouvelis 1991 / Ang-Piazzesi-Wei 2006).

Foundational: Estrella, A. & Hardouvelis, G. A. (1991). *The Term
Structure as a Predictor of Real Economic Activity*. J Finance
46(2), 555-576. DOI: https://doi.org/10.1111/j.1540-6261.1991.tb03775.x

Primary methodology: Ang, A., Piazzesi, M. & Wei, M. (2006).
*What Does the Yield Curve Tell Us about GDP Growth?*. J
Econometrics 131(1-2), 359-403.
DOI: https://doi.org/10.1016/j.jfineco.2005.05.005
"""

from __future__ import annotations

from alphakit.strategies.macro.yield_curve_regime_allocation.strategy import (
    YieldCurveRegimeAllocation,
)

__all__ = ["YieldCurveRegimeAllocation"]
