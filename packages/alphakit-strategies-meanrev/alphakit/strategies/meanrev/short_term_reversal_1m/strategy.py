"""Short-term (1-month) reversal — cross-sectional (Jegadeesh 1990).

Reference
---------
Jegadeesh, N. (1990). Evidence of Predictable Behavior of Security
Returns. *Journal of Finance*, 45(3), 881-898.
DOI: 10.1111/j.1540-6261.1990.tb05088.x.

Jegadeesh documented that stocks with the worst 1-month returns tend
to outperform over the following month, and vice versa. This is the
canonical short-term reversal anomaly. The strategy ranks assets by
their trailing 1-month return and goes long the bottom quintile /
short the top quintile.

Rules
-----
Cross-sectional:
  1. Compute trailing 1-month return for each asset
  2. Rank assets (lower return → higher rank)
  3. Long the lowest-return assets, short the highest-return assets
  4. Weights proportional to demeaned rank, normalized to sum ≈ 0
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class ShortTermReversal1M:
    """1-month short-term reversal — cross-sectional long/short."""

    name: str = "short_term_reversal_1m"
    family: str = "meanrev"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1111/j.1540-6261.1990.tb05088.x"  # Jegadeesh (1990)
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        lookback: int = 21,
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
            # Cross-sectional strategy needs at least 2 assets to rank
            return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

        # Trailing 1-month return
        ret = prices.pct_change(periods=self.lookback)

        # Cross-sectional rank: ascending (worst return → rank 1)
        # Use average method to handle ties
        ranks = ret.rank(axis=1, method="average", ascending=True)

        # Demean ranks to create long/short signal
        rank_mean = ranks.mean(axis=1)
        demeaned = ranks.sub(rank_mean, axis=0)

        # Normalize: divide by sum of absolute values to get weights
        abs_sum = demeaned.abs().sum(axis=1).replace(0.0, np.nan)
        weights = demeaned.div(abs_sum, axis=0)

        if self.long_only:
            weights = weights.clip(lower=0.0)
            # Re-normalize long-only to sum to 1
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
