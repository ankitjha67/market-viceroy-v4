"""Swap spread carry (Duarte, Longstaff & Yu 2007).

Reference
---------
Duarte, J., Longstaff, F.A. & Yu, F. (2007). Risk and Return in
Fixed-Income Arbitrage: Nickels in Front of a Steamroller? *Review
of Financial Studies*, 20(3), 769-811. DOI: 10.1093/rfs/hhl026.

The swap spread trade exploits the difference between swap rates
and Treasury yields. When the spread is unusually wide, receive
fixed in the swap (earn the higher rate) and short the Treasury
(pay the lower rate). The spread tends to mean-revert.

**Phase 1 proxy**: Without rate-curve data, uses rolling Z-score
of price spreads between rate-sensitive assets as a carry proxy.
See ADR-001.

Rules
-----
Cross-sectional across tenors:
  1. Compute carry proxy per asset pair
  2. Rank by proxy spread
  3. Dollar-neutral portfolio
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class SwapSpreadCarry:
    """Swap spread carry — cross-sectional across rate tenors."""

    name: str = "swap_spread_carry"
    family: str = "carry"
    asset_classes: tuple[str, ...] = ("future",)
    paper_doi: str = "10.1093/rfs/hhl026"  # Duarte, Longstaff & Yu (2007)
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        lookback: int = 63,
        long_only: bool = False,
    ) -> None:
        if lookback <= 0:
            raise ValueError(f"lookback must be positive, got {lookback}")
        self.lookback = lookback
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

        n_assets = len(prices.columns)
        if n_assets < 2:
            return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

        # Carry proxy: trailing return (spread carry approximation)
        carry_proxy = prices.pct_change(periods=self.lookback)

        ranks = carry_proxy.rank(axis=1, method="average", ascending=True)
        rank_mean = ranks.mean(axis=1)
        demeaned = ranks.sub(rank_mean, axis=0)
        abs_sum = demeaned.abs().sum(axis=1).replace(0.0, np.nan)
        weights = demeaned.div(abs_sum, axis=0)

        if self.long_only:
            weights = weights.clip(lower=0.0)
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
