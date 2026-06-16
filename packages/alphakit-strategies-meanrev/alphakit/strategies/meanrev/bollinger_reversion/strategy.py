"""Bollinger Band mean reversion (Bollinger 2001).

Reference
---------
Bollinger, J. (2001). *Bollinger on Bollinger Bands*.
McGraw-Hill. ISBN 0-07-137368-3.

Bollinger Bands place an upper band at SMA(period) + k * σ and a lower
band at SMA(period) − k * σ, where σ is the rolling standard deviation
over the same window. The mean-reversion signal goes long when price
touches the lower band (oversold) and short when price touches the
upper band (overbought). Position is exited (flat) when price reverts
to the SMA.

Rules
-----
For each asset independently:
  weight = −1/n  when price ≥ upper band  (overbought → short)
  weight = +1/n  when price ≤ lower band  (oversold → long)
  weight =  0    otherwise                 (inside bands → flat)
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class BollingerReversion:
    """Bollinger Band mean reversion — buy lower band, sell upper band."""

    name: str = "bollinger_reversion"
    family: str = "meanrev"
    asset_classes: tuple[str, ...] = ("equity", "future", "fx", "commodity", "crypto")
    paper_doi: str = "0-07-137368-3"  # ISBN of Bollinger (2001)
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        period: int = 20,
        num_std: float = 2.0,
        long_only: bool = False,
    ) -> None:
        if period <= 1:
            raise ValueError(f"period must be > 1, got {period}")
        if num_std <= 0.0:
            raise ValueError(f"num_std must be positive, got {num_std}")
        self.period = period
        self.num_std = num_std
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

        sma = prices.rolling(window=self.period, min_periods=self.period).mean()
        std = prices.rolling(window=self.period, min_periods=self.period).std(ddof=1)

        upper = sma + self.num_std * std
        lower = sma - self.num_std * std

        # Oversold (below lower) → long (+1); overbought (above upper) → short (−1)
        signal = pd.DataFrame(
            np.where(
                prices.to_numpy() <= lower.to_numpy(),
                1.0,
                np.where(prices.to_numpy() >= upper.to_numpy(), -1.0, 0.0),
            ),
            index=prices.index,
            columns=prices.columns,
        )

        if self.long_only:
            signal = signal.clip(lower=0.0)

        n = len(prices.columns)
        weights = signal / n
        return cast(pd.DataFrame, weights.fillna(0.0))
