"""Greenblatt magic formula (Greenblatt 2006).

Reference
---------
Greenblatt, J. (2006). *The Little Book That Beats the Market*.
Wiley. ISBN 978-0-471-73306-5.

The magic formula ranks stocks by the sum of two ranks: earnings
yield (EBIT/EV) and return on capital (EBIT/net fixed assets +
working capital). Long the lowest combined rank (cheap + quality).

**Phase 1 proxy**: Value rank = negative trailing 3-year return.
Quality rank = volatility-adjusted trailing 1-year return. Combined
rank = sum. See ADR-001.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class MagicFormula:
    """Greenblatt magic formula — combined value + quality ranking proxy."""

    name: str = "magic_formula"
    family: str = "value"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "978-0-471-73306-5"
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        value_lookback: int = 756,
        quality_lookback: int = 252,
        long_only: bool = False,
    ) -> None:
        if value_lookback <= 0:
            raise ValueError(f"value_lookback must be positive, got {value_lookback}")
        if quality_lookback <= 0:
            raise ValueError(f"quality_lookback must be positive, got {quality_lookback}")
        self.value_lookback = value_lookback
        self.quality_lookback = quality_lookback
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

        # Value rank: negative trailing long-term return (reversal)
        value_proxy = -prices.pct_change(periods=self.value_lookback)
        value_rank = value_proxy.rank(axis=1, method="average", ascending=True)

        # Quality rank: vol-adjusted trailing return (high = better quality)
        daily_ret = prices.pct_change()
        trailing_ret = prices.pct_change(periods=self.quality_lookback)
        trailing_vol = daily_ret.rolling(
            window=self.quality_lookback, min_periods=self.quality_lookback
        ).std(ddof=1)
        quality_proxy = trailing_ret / trailing_vol.replace(0.0, np.nan)
        quality_rank = quality_proxy.rank(axis=1, method="average", ascending=True)

        # Combined rank: sum of value and quality ranks
        combined_rank = value_rank + quality_rank

        rank_mean = combined_rank.mean(axis=1)
        demeaned = combined_rank.sub(rank_mean, axis=0)
        abs_sum = demeaned.abs().sum(axis=1).replace(0.0, np.nan)
        weights = demeaned.div(abs_sum, axis=0)

        if self.long_only:
            weights = weights.clip(lower=0.0)
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
