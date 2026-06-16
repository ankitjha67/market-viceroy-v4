"""Inflation-regime 3-cell allocation (Neville et al. 2021 / Erb-Harvey 2006).

Foundational: Neville, H., Draaisma, T., Funnell, B., Harvey, C. R. &
Van Hemert, O. (2021). *The Best Strategies for Inflationary Times*.
Journal of Portfolio Management Quantitative Special Issue.
DOI: https://doi.org/10.3905/jpm.2021.1.290

Primary methodology: Erb, C. B. & Harvey, C. R. (2006). *The Strategic
and Tactical Value of Commodity Futures*. Financial Analysts Journal
62(2), 69-97.
DOI: https://doi.org/10.2469/faj.v62.n2.4080
"""

from __future__ import annotations

from alphakit.strategies.macro.inflation_regime_allocation.strategy import (
    InflationRegimeAllocation,
)

__all__ = ["InflationRegimeAllocation"]
