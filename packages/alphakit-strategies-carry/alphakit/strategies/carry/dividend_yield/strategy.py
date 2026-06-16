"""Dividend yield carry (Litzenberger & Ramaswamy 1979).

Reference
---------
Litzenberger, R.H. & Ramaswamy, K. (1979). The effect of personal
taxes and dividends on capital asset prices. *Journal of Financial
Economics*, 7(2), 163-195. DOI: 10.1016/0304-405X(79)90012-6.

Stocks with higher dividend yields tend to outperform on a total-
return basis. This is the equity carry analogue of FX carry: the
dividend yield is the "interest rate" that accrues to equity holders.

**Phase 1 proxy**: Since the protocol provides only close prices
(no dividend data), this implementation uses the trailing 252-day
return volatility-adjusted as a proxy. Low-volatility, positive-
return stocks are treated as "high dividend yield." This is a known
simplification (see ADR-001).

Rules
-----
Cross-sectional:
  1. Compute carry proxy per asset
  2. Rank: highest proxy → highest carry
  3. Long top decile, short bottom decile
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class DividendYield:
    """Dividend yield carry — cross-sectional long/short on yield proxy."""

    name: str = "dividend_yield"
    family: str = "carry"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1016/0304-405X(79)90012-6"  # Litzenberger & Ramaswamy (1979)
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        lookback: int = 252,
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

        # Dividend yield proxy: trailing return / trailing volatility
        # High return + low vol → proxy for high, stable dividend payers
        trailing_ret = prices.pct_change(periods=self.lookback)
        daily_ret = prices.pct_change()
        trailing_vol = daily_ret.rolling(window=self.lookback, min_periods=self.lookback).std(
            ddof=1
        )
        carry_proxy = trailing_ret / trailing_vol.replace(0.0, np.nan)

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
