"""Long-only Minimum-Variance portfolio on stocks / bonds / commodities.

Foundational: Clarke, R., de Silva, H. & Thorley, S. (2006).
*Minimum-Variance Portfolios in the U.S. Equity Market*. J Portfolio
Management 33(1), 10-24. DOI: https://doi.org/10.3905/jpm.2006.661366

Primary methodology: Haugen, R. A. & Baker, N. L. (1991).
*The Efficient Market Inefficiency of Capitalization-Weighted Stock
Portfolios*. J Portfolio Management 17(3), 35-40.
DOI: https://doi.org/10.3905/jpm.1991.409335
"""

from __future__ import annotations

from alphakit.strategies.macro.min_variance_gtaa.strategy import MinVarianceGtaa

__all__ = ["MinVarianceGtaa"]
