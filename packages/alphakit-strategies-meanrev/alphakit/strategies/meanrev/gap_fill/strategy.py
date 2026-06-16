"""Opening gap fill intraday strategy (Brock, Lakonishok & LeBaron 1992 baseline).

Reference
---------
Brock, W., Lakonishok, J. & LeBaron, B. (1992). Simple Technical
Trading Rules and the Stochastic Properties of Stock Returns.
*Journal of Finance*, 47(5), 1731-1764.

Gap fill is a practitioner strategy: when price "gaps" away from
the prior close (large overnight move), it tends to partially fill
back towards the prior close during the session. Since the protocol
uses daily closes, this implementation approximates the gap as the
difference between the current return and a slow-moving average of
recent returns, and trades the mean reversion of that gap.

Rules
-----
For each asset independently:
  1. Compute daily return
  2. Compute rolling mean return as "expected" return
  3. Gap = actual return − expected return
  4. If gap > threshold → overbought → short
  5. If gap < −threshold → oversold → long
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class GapFill:
    """Opening gap fill mean reversion — fade large overnight moves."""

    name: str = "gap_fill"
    family: str = "meanrev"
    asset_classes: tuple[str, ...] = ("equity", "future", "fx", "crypto")
    paper_doi: str = "10.1111/j.1540-6261.1992.tb04681.x"  # BLL (1992)
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        lookback: int = 20,
        gap_threshold: float = 2.0,
        long_only: bool = False,
    ) -> None:
        if lookback <= 1:
            raise ValueError(f"lookback must be > 1, got {lookback}")
        if gap_threshold <= 0.0:
            raise ValueError(f"gap_threshold must be positive, got {gap_threshold}")
        self.lookback = lookback
        self.gap_threshold = gap_threshold
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

        daily_ret = prices.pct_change()
        rolling_mean = daily_ret.rolling(window=self.lookback, min_periods=self.lookback).mean()
        rolling_std = daily_ret.rolling(window=self.lookback, min_periods=self.lookback).std(ddof=1)

        # Gap Z-score: how unusual is today's return?
        gap_z = (daily_ret - rolling_mean) / rolling_std.replace(0.0, np.nan)

        gap_np = gap_z.to_numpy()
        signal = pd.DataFrame(
            np.where(
                gap_np <= -self.gap_threshold,
                1.0,
                np.where(gap_np >= self.gap_threshold, -1.0, 0.0),
            ),
            index=prices.index,
            columns=prices.columns,
        )

        if self.long_only:
            signal = signal.clip(lower=0.0)

        n = len(prices.columns)
        weights = signal / n
        return cast(pd.DataFrame, weights.fillna(0.0))
