"""Shareholder yield (Faber 2013).

Reference
---------
Faber, M.T. (2013). *Shareholder Yield: A Better Approach to
Dividend Investing*. Cambria Investment Management.
ISBN 978-0-988-67950-0.

**Phase 1 proxy**: Trailing stability of positive returns as
shareholder-yield proxy. Stocks with consistent positive returns
are proxies for steady capital return to shareholders. See ADR-001.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class ShareholderYield:
    """Shareholder yield — cross-sectional via return stability proxy."""

    name: str = "shareholder_yield"
    family: str = "value"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "978-0-988-67950-0"
    rebalance_frequency: str = "monthly"

    def __init__(self, *, lookback: int = 252, long_only: bool = False) -> None:
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

        # Shareholder yield proxy: fraction of positive monthly returns
        # in the lookback window (steady positive returns ≈ dividends + buybacks)
        monthly_ret = prices.pct_change(periods=21)
        positive_frac = monthly_ret.rolling(window=self.lookback, min_periods=self.lookback).apply(
            lambda x: float(np.mean(x > 0)), raw=True
        )

        ranks = positive_frac.rank(axis=1, method="average", ascending=True)
        rank_mean = ranks.mean(axis=1)
        demeaned = ranks.sub(rank_mean, axis=0)
        abs_sum = demeaned.abs().sum(axis=1).replace(0.0, np.nan)
        weights = demeaned.div(abs_sum, axis=0)

        if self.long_only:
            weights = weights.clip(lower=0.0)
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
