"""Federal-policy-tilt 2-cell regime allocation (Conover et al. 2008 / Jensen-Mercer-Johnson 1996).

Foundational: Conover, C. M., Jensen, G. R., Johnson, R. R. & Mercer,
J. M. (2008). *Sector Rotation and Monetary Conditions*. Journal of
Investing 17(2), 34-46.
DOI: https://doi.org/10.3905/joi.2008.17.4.61

Primary methodology: Jensen, G. R., Mercer, J. M. & Johnson, R. R.
(1996). *Business Conditions, Monetary Policy, and Expected Security
Returns*. Journal of Financial Economics 40(2), 213-237.
DOI: https://doi.org/10.1016/0304-405X(96)00875-X
"""

from __future__ import annotations

from alphakit.strategies.macro.fed_policy_tilt.strategy import (
    FedPolicyTilt,
)

__all__ = ["FedPolicyTilt"]
