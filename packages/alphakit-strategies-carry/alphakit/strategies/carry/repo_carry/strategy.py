"""Repo carry (Duffie 1996).

Reference
---------
Duffie, D. (1996). Special Repo Rates. *Journal of Finance*, 51(2),
493-526. DOI: 10.1111/j.1540-6261.1996.tb02708.x.

The repo carry strategy exploits the spread between general
collateral (GC) and special repo rates. Securities "on special"
have lower repo rates, creating an arbitrage for holders.

**Phase 1 proxy**: Without actual repo rate data, this implementation
uses the rolling mean-reversion of bond-like assets as a proxy.
Assets whose price has deviated below their recent mean are treated
as "on special" (high demand for borrowing → low repo rate → carry
opportunity). See ADR-001.

Rules
-----
For each asset:
  1. Z-score of price relative to rolling mean
  2. Negative Z → asset is "on special" → long carry opportunity
  3. Positive Z → normal GC → no carry
  4. Weight proportional to negative Z-score
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class RepoCarry:
    """Repo carry — GC vs special repo rate arbitrage proxy."""

    name: str = "repo_carry"
    family: str = "carry"
    asset_classes: tuple[str, ...] = ("future",)
    paper_doi: str = "10.1111/j.1540-6261.1996.tb02708.x"  # Duffie (1996)
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        lookback: int = 60,
        threshold: float = 1.0,
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
        # Negative Z → "on special" → long carry; positive Z → short carry
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
