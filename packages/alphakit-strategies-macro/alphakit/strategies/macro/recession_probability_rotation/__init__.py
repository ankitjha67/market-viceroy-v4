"""Recession-probability-driven rotation across equity / bonds / gold.

Foundational: Estrella, A. & Mishkin, F. S. (1998).
*Predicting U.S. Recessions: Financial Variables as Leading
Indicators*. Review of Economics and Statistics 80(1), 45-61.
DOI: https://doi.org/10.1162/003465398557320

Primary methodology: Wright, J. H. (2006). *The Yield Curve and
Predicting Recessions*. Federal Reserve Board FEDS Working Paper
2006-07. URL:
https://www.federalreserve.gov/pubs/feds/2006/200607/200607pap.pdf
"""

from __future__ import annotations

from alphakit.strategies.macro.recession_probability_rotation.strategy import (
    RecessionProbabilityRotation,
)

__all__ = ["RecessionProbabilityRotation"]
