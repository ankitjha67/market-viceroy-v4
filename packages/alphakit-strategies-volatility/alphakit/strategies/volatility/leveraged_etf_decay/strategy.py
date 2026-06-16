"""Leveraged ETF decay (Cheng & Madhavan 2009).

Reference
---------
Cheng, M. & Madhavan, A. (2009). The Dynamics of Leveraged and
Inverse Exchange-Traded Funds. *Journal of Investment Management*,
7(4), 43-62. DOI: 10.3905/joi.2009.18.4.043.

Leveraged ETFs suffer from volatility drag due to daily rebalancing.
This strategy harvests the decay by going short when vol is high
(decay is proportional to variance).

Proxy: Short exposure proportional to trailing variance.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class LeveragedETFDecay:
    """Leveraged ETF vol drag — short high-vol assets to harvest decay."""

    name: str = "leveraged_etf_decay"
    family: str = "volatility"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.3905/joi.2009.18.4.043"
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        vol_lookback: int = 20,
        vol_threshold: float = 0.20,
        long_only: bool = False,
    ) -> None:
        if vol_lookback <= 1:
            raise ValueError(f"vol_lookback must be > 1, got {vol_lookback}")
        if vol_threshold <= 0.0:
            raise ValueError(f"vol_threshold must be positive, got {vol_threshold}")
        self.vol_lookback = vol_lookback
        self.vol_threshold = vol_threshold
        self.long_only = long_only

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        n = len(prices.columns)
        daily_ret = prices.pct_change()
        realized_vol = daily_ret.rolling(
            window=self.vol_lookback, min_periods=self.vol_lookback
        ).std(ddof=1) * np.sqrt(252)

        vol_np = realized_vol.to_numpy()
        # Short when vol > threshold (decay is high); flat otherwise
        signal = pd.DataFrame(
            np.where(vol_np > self.vol_threshold, -1.0, 0.0),
            index=prices.index,
            columns=prices.columns,
        )
        if self.long_only:
            signal = signal.clip(lower=0.0)
        return cast(pd.DataFrame, (signal / n).fillna(0.0))
