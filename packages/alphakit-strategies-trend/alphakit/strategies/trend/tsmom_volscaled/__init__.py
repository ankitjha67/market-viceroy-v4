"""Time-series momentum with continuous vol-scaled signal.

Reference implementation of Hurst, Ooi & Pedersen (2017),
*A Century of Evidence on Trend-Following Investing*. AQR / SSRN 2993026.
DOI: https://doi.org/10.2139/ssrn.2993026
"""

from __future__ import annotations

from alphakit.strategies.trend.tsmom_volscaled.strategy import TimeSeriesMomentumVolScaled

__all__ = ["TimeSeriesMomentumVolScaled"]
