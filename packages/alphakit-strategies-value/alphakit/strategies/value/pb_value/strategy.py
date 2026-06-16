"""Price-to-book value (Fama & French 1992).

Reference
---------
Fama, E.F. & French, K.R. (1992). The Cross-Section of Expected
Stock Returns. *Journal of Finance*, 47(2), 427-465.
DOI: 10.1111/j.1540-6261.1992.tb04398.x.

**Phase 1 proxy**: Long-term (3-year) price reversal as value proxy.
Stocks that have underperformed over 3 years tend to have low P/B
ratios. See ADR-001.

Rules
-----
Cross-sectional:
  1. Compute trailing 3-year return (value proxy: low return ≈ low P/B)
  2. Rank ascending: lowest return → highest value rank
  3. Long top value, short bottom value (growth), dollar-neutral
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class PBValue:
    """Price-to-book value — cross-sectional long/short via reversal proxy."""

    name: str = "pb_value"
    family: str = "value"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1111/j.1540-6261.1992.tb04398.x"
    rebalance_frequency: str = "monthly"

    def __init__(self, *, lookback: int = 756, long_only: bool = False) -> None:
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

        # Value proxy: negative of trailing return (low return ≈ cheap ≈ high value)
        trailing_ret = prices.pct_change(periods=self.lookback)
        value_proxy = -trailing_ret

        ranks = value_proxy.rank(axis=1, method="average", ascending=True)
        rank_mean = ranks.mean(axis=1)
        demeaned = ranks.sub(rank_mean, axis=0)
        abs_sum = demeaned.abs().sum(axis=1).replace(0.0, np.nan)
        weights = demeaned.div(abs_sum, axis=0)

        if self.long_only:
            weights = weights.clip(lower=0.0)
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
