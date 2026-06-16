"""Contrarian COT speculator-positioning trade on commodity futures.

Foundational: Bessembinder, H. (1992), *Systematic Risk, Hedging
Pressure, and Risk Premiums in Futures Markets*, Review of Financial
Studies 5(4), 637–667.
DOI: https://doi.org/10.1093/rfs/5.4.637

Primary methodology: de Roon, F. A., Nijman, T. E. & Veld, C.
(2000), *Hedging Pressure Effects in Futures Markets*, Journal of
Finance 55(3), 1437–1456. Documents that **commercial hedging
pressure** (the inverse of non-commercial speculator positioning)
predicts futures returns: when speculators are extremely long,
expected returns are negative.
DOI: https://doi.org/10.1111/0022-1082.00253
"""

from __future__ import annotations

from alphakit.strategies.commodity.cot_speculator_position.strategy import (
    COTSpeculatorPosition,
)

__all__ = ["COTSpeculatorPosition"]
