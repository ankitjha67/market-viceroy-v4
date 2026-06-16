"""cash_secured_put_systematic — single-leg systematic 1-month 5 % OTM put write.

Foundational: Whaley, R. E. (2002),
*Return and Risk of CBOE Buy Write Monthly Index*, Journal of
Derivatives 10(2), 35-42.
DOI: https://doi.org/10.3905/jod.2002.319188

Primary methodology: Israelov, R. & Nielsen, L. N. (2014),
*Covered Call Strategies: One Fact and Eight Myths*, Financial
Analysts Journal 70(6), 23-31.
DOI: https://doi.org/10.2469/faj.v70.n6.5
"""

from __future__ import annotations

from alphakit.strategies.options.cash_secured_put_systematic.strategy import (
    CashSecuredPutSystematic,
)

__all__ = ["CashSecuredPutSystematic"]
