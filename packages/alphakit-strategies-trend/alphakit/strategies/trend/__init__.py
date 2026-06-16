"""Trend-following strategies.

Phase 0 ships one reference strategy: ``tsmom_12_1`` (Moskowitz, Ooi,
Pedersen 2012). Phase 1 adds 14 more — cross-sectional momentum, dual
momentum, residual momentum, 52-week high, SMA/EMA crosses, Donchian,
Turtle, Ichimoku, SuperTrend — per the master plan section 4.2.
"""

from __future__ import annotations

from alphakit.strategies.trend.donchian_breakout_20.strategy import DonchianBreakout20
from alphakit.strategies.trend.donchian_breakout_55.strategy import DonchianBreakout55
from alphakit.strategies.trend.dual_momentum_gem.strategy import DualMomentumGEM
from alphakit.strategies.trend.ema_cross_12_26.strategy import EMACross1226
from alphakit.strategies.trend.fifty_two_week_high.strategy import FiftyTwoWeekHigh
from alphakit.strategies.trend.frog_in_the_pan.strategy import FrogInThePan
from alphakit.strategies.trend.ichimoku_cloud.strategy import IchimokuCloud
from alphakit.strategies.trend.residual_momentum.strategy import ResidualMomentum
from alphakit.strategies.trend.sma_cross_10_30.strategy import SMACross1030
from alphakit.strategies.trend.sma_cross_50_200.strategy import SMACross50200
from alphakit.strategies.trend.supertrend.strategy import Supertrend
from alphakit.strategies.trend.tsmom_12_1.strategy import TimeSeriesMomentum12m1m
from alphakit.strategies.trend.tsmom_volscaled.strategy import TimeSeriesMomentumVolScaled
from alphakit.strategies.trend.turtle_full.strategy import TurtleFull
from alphakit.strategies.trend.xs_momentum_jt.strategy import CrossSectionalMomentumJT

__all__ = [
    "CrossSectionalMomentumJT",
    "DonchianBreakout20",
    "DonchianBreakout55",
    "DualMomentumGEM",
    "EMACross1226",
    "FiftyTwoWeekHigh",
    "FrogInThePan",
    "IchimokuCloud",
    "ResidualMomentum",
    "SMACross1030",
    "SMACross50200",
    "Supertrend",
    "TimeSeriesMomentum12m1m",
    "TimeSeriesMomentumVolScaled",
    "TurtleFull",
]
