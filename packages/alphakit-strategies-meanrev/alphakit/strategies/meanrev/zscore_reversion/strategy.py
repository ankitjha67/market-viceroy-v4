"""Rolling Z-score mean reversion (Chan 2013).

Reference
---------
Chan, E.P. (2013). *Algorithmic Trading: Winning Strategies and
Their Rationale*. Wiley. ISBN 978-1-118-46014-6.

A rolling Z-score normalizes price by subtracting the rolling mean
and dividing by the rolling standard deviation. When the Z-score
exceeds ±threshold (default ±2), the asset is statistically
dislocated from its recent mean and is expected to revert.

Rules
-----
For each asset independently:
  weight = +1/n  when Z-score ≤ −threshold  (undervalued → long)
  weight = −1/n  when Z-score ≥ +threshold  (overvalued → short)
  weight =  0    otherwise
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class ZScoreReversion:
    """Rolling Z-score mean reversion — buy below −2σ, sell above +2σ."""

    name: str = "zscore_reversion"
    family: str = "meanrev"
    asset_classes: tuple[str, ...] = ("equity", "future", "fx", "commodity", "crypto")
    paper_doi: str = "978-1-118-46014-6"  # ISBN of Chan (2013)
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        lookback: int = 20,
        threshold: float = 2.0,
        long_only: bool = False,
    ) -> None:
        if lookback <= 1:
            raise ValueError(f"lookback must be > 1, got {lookback}")
        if threshold <= 0.0:
            raise ValueError(f"threshold must be positive, got {threshold}")
        self.lookback = lookback
        self.threshold = threshold
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

        rolling_mean = prices.rolling(window=self.lookback, min_periods=self.lookback).mean()
        rolling_std = prices.rolling(window=self.lookback, min_periods=self.lookback).std(ddof=1)

        zscore = (prices - rolling_mean) / rolling_std.replace(0.0, np.nan)

        z_np = zscore.to_numpy()
        signal = pd.DataFrame(
            np.where(
                z_np <= -self.threshold,
                1.0,
                np.where(z_np >= self.threshold, -1.0, 0.0),
            ),
            index=prices.index,
            columns=prices.columns,
        )

        if self.long_only:
            signal = signal.clip(lower=0.0)

        n = len(prices.columns)
        weights = signal / n
        return cast(pd.DataFrame, weights.fillna(0.0))
