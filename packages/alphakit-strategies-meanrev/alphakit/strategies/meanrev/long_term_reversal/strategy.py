"""Long-term (3-5 year) reversal (DeBondt & Thaler 1985).

Reference
---------
DeBondt, W.F.M. & Thaler, R. (1985). Does the Stock Market
Overreact? *Journal of Finance*, 40(3), 793-805.
DOI: 10.1111/j.1540-6261.1985.tb05004.x.

DeBondt and Thaler showed that stocks with the worst 3-5 year
returns ("losers") subsequently outperform, and past "winners"
underperform. This is the long-term reversal effect, driven by
investor overreaction to past performance.

Rules
-----
Cross-sectional:
  1. Compute trailing N-year return for each asset
  2. Rank assets — worst performers get highest long weight
  3. Dollar-neutral: long losers, short winners
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class LongTermReversal:
    """3-5 year long-term reversal — cross-sectional contrarian."""

    name: str = "long_term_reversal"
    family: str = "meanrev"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1111/j.1540-6261.1985.tb05004.x"  # DeBondt & Thaler (1985)
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        lookback_years: int = 3,
        long_only: bool = False,
    ) -> None:
        if lookback_years <= 0:
            raise ValueError(f"lookback_years must be positive, got {lookback_years}")
        self.lookback_years = lookback_years
        self.lookback = lookback_years * 252
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

        ret = prices.pct_change(periods=self.lookback)
        ranks = ret.rank(axis=1, method="average", ascending=True)
        rank_mean = ranks.mean(axis=1)
        demeaned = ranks.sub(rank_mean, axis=0)
        abs_sum = demeaned.abs().sum(axis=1).replace(0.0, np.nan)
        weights = demeaned.div(abs_sum, axis=0)

        if self.long_only:
            weights = weights.clip(lower=0.0)
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
