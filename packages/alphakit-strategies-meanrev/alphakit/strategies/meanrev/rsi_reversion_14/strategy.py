"""Wilder RSI(14) mean reversion (Wilder 1978).

Reference
---------
Wilder, J.W. (1978). *New Concepts in Technical Trading Systems*.
Trend Research. ISBN 0-89459-027-8.

The classic 14-period RSI identifies overbought (>70) and oversold
(<30) conditions. Unlike the aggressive RSI(2), the 14-period window
smooths out 1-2 day noise and fires on multi-week dislocations.

Rules
-----
For each asset independently:
  weight = +1/n  when RSI(14) < lower_threshold  (oversold → long)
  weight = −1/n  when RSI(14) > upper_threshold  (overbought → short)
  weight =  0    otherwise
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class RSIReversion14:
    """Wilder RSI(14) mean reversion — buy <30, sell >70."""

    name: str = "rsi_reversion_14"
    family: str = "meanrev"
    asset_classes: tuple[str, ...] = ("equity", "future", "fx", "commodity", "crypto")
    paper_doi: str = "0-89459-027-8"  # ISBN of Wilder (1978)
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        period: int = 14,
        lower_threshold: float = 30.0,
        upper_threshold: float = 70.0,
        long_only: bool = False,
    ) -> None:
        if period <= 0:
            raise ValueError(f"period must be positive, got {period}")
        if not (0.0 < lower_threshold < upper_threshold < 100.0):
            raise ValueError(
                f"thresholds must satisfy 0 < lower ({lower_threshold}) "
                f"< upper ({upper_threshold}) < 100"
            )
        self.period = period
        self.lower_threshold = lower_threshold
        self.upper_threshold = upper_threshold
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

        delta = prices.diff()
        gain = delta.clip(lower=0.0)
        loss = (-delta).clip(lower=0.0)

        avg_gain = gain.ewm(alpha=1.0 / self.period, min_periods=self.period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / self.period, min_periods=self.period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0.0, np.nan)
        rsi = 100.0 - 100.0 / (1.0 + rs)

        rsi_np = rsi.to_numpy()
        signal = pd.DataFrame(
            np.where(
                rsi_np <= self.lower_threshold,
                1.0,
                np.where(rsi_np >= self.upper_threshold, -1.0, 0.0),
            ),
            index=prices.index,
            columns=prices.columns,
        )

        if self.long_only:
            signal = signal.clip(lower=0.0)

        n = len(prices.columns)
        weights = signal / n
        return cast(pd.DataFrame, weights.fillna(0.0))
