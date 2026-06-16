"""WTI crude-oil long-only carry on the front-vs-next-month curve slope.

Foundational: Gorton, G. & Rouwenhorst, K. G. (2006), *Facts and
Fantasies about Commodity Futures*, Financial Analysts Journal 62(2),
47–68. DOI: https://doi.org/10.2469/faj.v62.n2.4083

Primary methodology: Erb, C. B. & Harvey, C. R. (2006), *The Strategic
and Tactical Value of Commodity Futures*, Financial Analysts Journal
62(2), 69–97. Section III ("The Term Structure Story") documents the
relationship between curve slope and excess returns.
DOI: https://doi.org/10.2469/faj.v62.n2.4084
"""

from __future__ import annotations

from alphakit.strategies.commodity.wti_backwardation_carry.strategy import (
    WTIBackwardationCarry,
)

__all__ = ["WTIBackwardationCarry"]
