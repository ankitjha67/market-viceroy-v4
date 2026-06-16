"""EV/EBITDA value (Loughran & Wellman 2011).

Reference
---------
Loughran, T. & Wellman, J.W. (2011). New Evidence on the Relation
Between the Enterprise Multiple and Average Stock Returns. *Journal
of Financial and Quantitative Analysis*, 46(6), 1693-1717.
DOI: 10.1017/S0022109011000305.

**Phase 1 proxy**: Long-term reversal as EBITDA/EV proxy. See ADR-001.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class EVEbitda:
    """EV/EBITDA value — cross-sectional long/short via reversal proxy."""

    name: str = "ev_ebitda"
    family: str = "value"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1017/S0022109011000305"
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

        value_proxy = -prices.pct_change(periods=self.lookback)

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
