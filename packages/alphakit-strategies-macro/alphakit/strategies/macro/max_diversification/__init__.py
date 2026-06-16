"""Maximum-Diversification Portfolio on stocks / bonds / commodities.

Foundational: Choueifaty, Y. & Coignard, Y. (2008).
*Toward Maximum Diversification*. J Portfolio Management 35(1),
40-51. DOI: https://doi.org/10.3905/JPM.2008.35.1.40

Primary methodology: Choueifaty, Y., Froidure, T. & Reynier, J.
(2013). *Properties of the Most Diversified Portfolio*.
J Investment Management 11(3), 1-32. SSRN 1895459.
DOI: https://doi.org/10.2139/ssrn.1895459
"""

from __future__ import annotations

from alphakit.strategies.macro.max_diversification.strategy import MaxDiversification

__all__ = ["MaxDiversification"]
