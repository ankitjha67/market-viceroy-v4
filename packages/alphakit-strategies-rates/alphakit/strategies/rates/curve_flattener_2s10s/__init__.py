"""2s10s curve flattener — mean-reversion on the log-price spread.

Mirror image of CurveSteepener2s10s.

Foundational: Litterman & Scheinkman (1991),
*Common Factors Affecting Bond Returns*, Journal of Fixed Income 1(1).

Primary methodology: Cochrane & Piazzesi (2005),
*Bond Risk Premia*, American Economic Review 95(1), 138–160.
DOI: https://doi.org/10.1257/0002828053828581
"""

from __future__ import annotations

from alphakit.strategies.rates.curve_flattener_2s10s.strategy import CurveFlattener2s10s

__all__ = ["CurveFlattener2s10s"]
