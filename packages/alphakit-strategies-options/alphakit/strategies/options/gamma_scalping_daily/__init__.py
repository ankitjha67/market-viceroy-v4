"""gamma_scalping_daily — daily delta-hedged straddle (Sinclair 2008 practitioner framing).

Foundational: Hull, J. C. & White, A. (1987),
*The pricing of options on assets with stochastic volatilities*,
Journal of Finance 42(2), 281-300.
DOI: https://doi.org/10.1111/j.1540-6261.1987.tb02568.x

Primary methodology: Sinclair, E. (2008),
*Volatility Trading*. John Wiley & Sons. ISBN 978-0470181998.
(Book, no DOI; cited via ISBN.)
"""

from __future__ import annotations

from alphakit.strategies.options.gamma_scalping_daily.strategy import GammaScalpingDaily

__all__ = ["GammaScalpingDaily"]
