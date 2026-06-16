"""Quality minus junk + value (Asness, Frazzini & Pedersen 2013).

Reference
---------
Asness, C.S., Frazzini, A. & Pedersen, L.H. (2019). Quality Minus
Junk. *Review of Accounting Studies*, 24, 34-112.
DOI: 10.1007/s11142-018-9470-2.

**Phase 1 proxy**: Quality = low-vol + positive-trend + momentum.
Value = long-term reversal. Combined cross-sectional ranking.
See ADR-001.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class QualityValue:
    """Quality-value composite — combined quality + value ranking proxy."""

    name: str = "quality_value"
    family: str = "value"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1007/s11142-018-9470-2"
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

        daily_ret = prices.pct_change()

        # Value rank: reversal
        value_proxy = -prices.pct_change(periods=self.value_lookback)
        value_rank = value_proxy.rank(axis=1, method="average", ascending=True)

        # Quality rank: low-vol + positive momentum
        vol = daily_ret.rolling(
            window=self.quality_lookback, min_periods=self.quality_lookback
        ).std(ddof=1)
        low_vol_rank = (-vol).rank(axis=1, method="average", ascending=True)
        mom = prices.pct_change(periods=self.quality_lookback)
        mom_rank = mom.rank(axis=1, method="average", ascending=True)
        quality_rank = low_vol_rank + mom_rank

        combined = value_rank + quality_rank

        rank_mean = combined.mean(axis=1)
        demeaned = combined.sub(rank_mean, axis=0)
        abs_sum = demeaned.abs().sum(axis=1).replace(0.0, np.nan)
        weights = demeaned.div(abs_sum, axis=0)

        if self.long_only:
            weights = weights.clip(lower=0.0)
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
