"""Value strategies.

Phase 1 ships 10 value strategies — P/B, P/E, EV/EBITDA, FCF yield,
shareholder yield, magic formula, Piotroski F-score proxy, Altman
Z-score proxy, quality-value composite, and country CAPE rotation —
per the master plan section 4.5.

Note: value strategies use price-derived proxies for fundamental data.
See ADR-001 and ADR-002 for rationale.
"""

from __future__ import annotations

from alphakit.strategies.value.altman_zscore_proxy.strategy import AltmanZScoreProxy
from alphakit.strategies.value.country_cape_rotation.strategy import CountryCapeRotation
from alphakit.strategies.value.ev_ebitda.strategy import EVEbitda
from alphakit.strategies.value.fcf_yield.strategy import FCFYield
from alphakit.strategies.value.magic_formula.strategy import MagicFormula
from alphakit.strategies.value.pb_value.strategy import PBValue
from alphakit.strategies.value.pe_value.strategy import PEValue
from alphakit.strategies.value.piotroski_fscore_proxy.strategy import PiotroskiFScoreProxy
from alphakit.strategies.value.quality_value.strategy import QualityValue
from alphakit.strategies.value.shareholder_yield.strategy import ShareholderYield

__all__: list[str] = [
    "AltmanZScoreProxy",
    "CountryCapeRotation",
    "EVEbitda",
    "FCFYield",
    "MagicFormula",
    "PBValue",
    "PEValue",
    "PiotroskiFScoreProxy",
    "QualityValue",
    "ShareholderYield",
]
