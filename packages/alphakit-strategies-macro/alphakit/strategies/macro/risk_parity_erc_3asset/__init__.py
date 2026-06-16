"""Equal-Risk-Contribution (ERC) portfolio on stocks / bonds / commodities.

Foundational: Maillard, S., Roncalli, T. & Teiletche, J. (2010).
*The Properties of Equally Weighted Risk Contribution Portfolios*.
J Portfolio Management 36(4), 60-70.
DOI: https://doi.org/10.3905/jpm.2010.36.4.060

Primary methodology: Asness, C. S., Frazzini, A. & Pedersen, L. H.
(2012). *Leverage Aversion and Risk Parity*. Financial Analysts
Journal 68(1), 47-59.
DOI: https://doi.org/10.2469/faj.v68.n1.1
"""

from __future__ import annotations

from alphakit.strategies.macro.risk_parity_erc_3asset.strategy import (
    RiskParityErc3Asset,
)

__all__ = ["RiskParityErc3Asset"]
