"""Volatility strategies.

Phase 1 ships 10 volatility strategies — vol targeting, VIX term structure,
VIX roll short, leveraged ETF decay, covered call proxy, cash-secured put
proxy, wheel strategy proxy, iron condor proxy, short strangle proxy, and
VRP harvest — per the master plan section 4.6.

Options-based strategies use _proxy suffix per ADR-002.
"""

from __future__ import annotations

from alphakit.strategies.volatility.cash_secured_put_proxy.strategy import CashSecuredPutProxy
from alphakit.strategies.volatility.covered_call_proxy.strategy import CoveredCallProxy
from alphakit.strategies.volatility.iron_condor_systematic_proxy.strategy import (
    IronCondorSystematicProxy,
)
from alphakit.strategies.volatility.leveraged_etf_decay.strategy import LeveragedETFDecay
from alphakit.strategies.volatility.short_strangle_proxy.strategy import ShortStrangleProxy
from alphakit.strategies.volatility.vix_roll_short.strategy import VIXRollShort
from alphakit.strategies.volatility.vix_term_structure.strategy import VIXTermStructure
from alphakit.strategies.volatility.vol_targeting.strategy import VolTargeting
from alphakit.strategies.volatility.vrp_harvest.strategy import VRPHarvest
from alphakit.strategies.volatility.wheel_strategy_proxy.strategy import WheelStrategyProxy

__all__: list[str] = [
    "CashSecuredPutProxy",
    "CoveredCallProxy",
    "IronCondorSystematicProxy",
    "LeveragedETFDecay",
    "ShortStrangleProxy",
    "VIXRollShort",
    "VIXTermStructure",
    "VRPHarvest",
    "VolTargeting",
    "WheelStrategyProxy",
]
