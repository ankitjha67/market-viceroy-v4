"""variance_risk_premium_synthetic — short ATM straddle (Carr-Wu §2 variance-swap approximation).

Foundational: Bondarenko, O. (2014),
*Why Are Put Options So Expensive?*, Quarterly Journal of Finance
4(1), 1450015.
DOI: https://doi.org/10.1142/S2010139214500050

Primary methodology: Carr, P. & Wu, L. (2009),
*Variance Risk Premia*, Review of Financial Studies 22(3), 1311-1341.
DOI: https://doi.org/10.1093/rfs/hhn038
"""

from __future__ import annotations

from alphakit.strategies.options.variance_risk_premium_synthetic.strategy import (
    VarianceRiskPremiumSynthetic,
)

__all__ = ["VarianceRiskPremiumSynthetic"]
