"""Time-series momentum with 12-month lookback and 1-month skip.

Reference implementation of Moskowitz, Ooi & Pedersen (2012),
*Time Series Momentum*, Journal of Financial Economics 104(2), 228–250.
DOI: https://doi.org/10.1016/j.jfineco.2011.11.003
"""

from __future__ import annotations

from alphakit.strategies.trend.tsmom_12_1.strategy import TimeSeriesMomentum12m1m

__all__ = ["TimeSeriesMomentum12m1m"]
