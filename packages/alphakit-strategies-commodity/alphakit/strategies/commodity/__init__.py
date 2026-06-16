"""Commodity strategies — Phase 2 Session 2E.

Phase 2 target: 10 strategies on energy futures, metals, agricultural
commodities, CFTC speculator positioning, and cross-commodity carry
and momentum. Strategy classes are added to ``__all__`` as each
per-strategy commit lands within Session 2E.

The shipping count is 10 rather than the originally-planned 15:
``energy_weather_premium``, ``henry_hub_ttf_spread``,
``inventory_surprise``, ``calendar_spread_corn``, and
``coffee_weather_asymmetry`` were dropped under the Phase 2
honesty-check (no citable systematic-strategy papers, missing data
feeds for non-US markets, and folk-wisdom trades without academic
anchors). See ``docs/phase-2-amendments.md`` for the full audit
trail of the 5 drops.
"""

from __future__ import annotations

from alphakit.strategies.commodity.commodity_curve_carry.strategy import (
    CommodityCurveCarry,
)
from alphakit.strategies.commodity.commodity_tsmom.strategy import CommodityTSMOM12m1m
from alphakit.strategies.commodity.cot_speculator_position.strategy import (
    COTSpeculatorPosition,
)
from alphakit.strategies.commodity.crack_spread.strategy import CrackSpread
from alphakit.strategies.commodity.crush_spread.strategy import CrushSpread
from alphakit.strategies.commodity.grain_seasonality.strategy import GrainSeasonality
from alphakit.strategies.commodity.metals_momentum.strategy import MetalsMomentum
from alphakit.strategies.commodity.ng_contango_short.strategy import NGContangoShort
from alphakit.strategies.commodity.wti_backwardation_carry.strategy import (
    WTIBackwardationCarry,
)
from alphakit.strategies.commodity.wti_brent_spread.strategy import WTIBrentSpread

__all__ = [
    "COTSpeculatorPosition",
    "CommodityCurveCarry",
    "CommodityTSMOM12m1m",
    "CrackSpread",
    "CrushSpread",
    "GrainSeasonality",
    "MetalsMomentum",
    "NGContangoShort",
    "WTIBackwardationCarry",
    "WTIBrentSpread",
]
