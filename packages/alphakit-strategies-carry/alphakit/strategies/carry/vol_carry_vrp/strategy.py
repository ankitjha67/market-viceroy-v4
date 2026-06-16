"""Variance risk premium carry (Carr & Wu 2009).

Reference
---------
Carr, P. & Wu, L. (2009). Variance Risk Premia. *Review of
Financial Studies*, 22(3), 1311-1341. DOI: 10.1093/rfs/hhn038.

The variance risk premium (VRP) is the difference between implied
and realized variance. Systematically, implied vol exceeds realized
vol, so selling variance earns a carry-like premium.

**Phase 1 proxy**: Without options or VIX futures data, this
implementation estimates the VRP by comparing a fast volatility
estimate (recent 5-day realized vol) against a slow estimate (20-day
realized vol). When fast vol is below slow vol, the VRP is positive
(normal contango regime); the strategy goes long the asset to
capture the premium. When fast vol exceeds slow vol, the VRP is
negative (backwardation / crisis); the strategy goes flat or short.

Rules
-----
For each asset:
  1. Fast vol = 5-day realized vol (annualized)
  2. Slow vol = 20-day realized vol (annualized)
  3. VRP proxy = slow_vol − fast_vol
  4. If VRP proxy > 0: long (carry premium available)
  5. If VRP proxy < 0: short (vol spike, no carry)
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class VolCarryVRP:
    """Variance risk premium carry — short vol contango premium."""

    name: str = "vol_carry_vrp"
    family: str = "carry"
    asset_classes: tuple[str, ...] = ("equity", "future")
    paper_doi: str = "10.1093/rfs/hhn038"  # Carr & Wu (2009)
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        fast_vol_window: int = 5,
        slow_vol_window: int = 20,
        long_only: bool = False,
    ) -> None:
        if fast_vol_window <= 1:
            raise ValueError(f"fast_vol_window must be > 1, got {fast_vol_window}")
        if slow_vol_window <= 1:
            raise ValueError(f"slow_vol_window must be > 1, got {slow_vol_window}")
        if fast_vol_window >= slow_vol_window:
            raise ValueError(
                f"fast_vol_window ({fast_vol_window}) must be < slow_vol_window ({slow_vol_window})"
            )
        self.fast_vol_window = fast_vol_window
        self.slow_vol_window = slow_vol_window
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
        fast_vol = daily_ret.rolling(
            window=self.fast_vol_window, min_periods=self.fast_vol_window
        ).std(ddof=1)
        slow_vol = daily_ret.rolling(
            window=self.slow_vol_window, min_periods=self.slow_vol_window
        ).std(ddof=1)

        # VRP proxy: positive when slow_vol > fast_vol (contango)
        vrp = slow_vol - fast_vol

        n = len(prices.columns)
        signal = pd.DataFrame(
            np.where(vrp.to_numpy() > 0, 1.0, np.where(vrp.to_numpy() < 0, -1.0, 0.0)),
            index=prices.index,
            columns=prices.columns,
        )

        if self.long_only:
            signal = signal.clip(lower=0.0)

        weights = signal / n
        return cast(pd.DataFrame, weights.fillna(0.0))
