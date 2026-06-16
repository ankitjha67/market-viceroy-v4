"""Piotroski F-Score PROXY (Piotroski 2000).

Reference
---------
Piotroski, J.D. (2000). Value Investing: The Use of Historical
Financial Statement Information to Separate Winners from Losers.
*Journal of Accounting Research*, 38(Supplement), 1-41.
DOI: 10.2307/2672906.

**SEVERE DEVIATION — _proxy suffix applies (ADR-002).**

The real Piotroski F-Score is a 9-point score computed entirely from
accounting data. This proxy replaces all 9 signals with price-derived
indicators. This is NOT the F-Score. The canonical slug
piotroski_fscore is reserved for Phase 4 with real accounting data.

Proxy signals (9 price-based indicators, each scored 0 or 1):
  1. Positive 12-month return (profitability proxy)
  2. Positive 1-month return (recent profitability)
  3. 12m return > 6m return (improving profitability)
  4. Low trailing volatility (leverage/safety proxy)
  5. Decreasing volatility (improving safety)
  6. Above 200-day SMA (solvency proxy)
  7. Positive 3-month return (operating efficiency)
  8. 3m return > market average (relative efficiency)
  9. Low max drawdown in 12 months (liquidity proxy)
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class PiotroskiFScoreProxy:
    """Piotroski F-Score PROXY — 9-signal price-based composite."""

    name: str = "piotroski_fscore_proxy"
    family: str = "value"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.2307/2672906"
    rebalance_frequency: str = "monthly"

    def __init__(self, *, long_only: bool = False) -> None:
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

        ret_1m = prices.pct_change(periods=21)
        ret_3m = prices.pct_change(periods=63)
        ret_6m = prices.pct_change(periods=126)
        ret_12m = prices.pct_change(periods=252)
        daily_ret = prices.pct_change()
        vol_12m = daily_ret.rolling(window=252, min_periods=252).std(ddof=1)
        vol_6m = daily_ret.rolling(window=126, min_periods=126).std(ddof=1)
        sma_200 = prices.rolling(window=200, min_periods=200).mean()

        # Rolling max drawdown (12-month)
        rolling_max = prices.rolling(window=252, min_periods=252).max()
        drawdown = (prices - rolling_max) / rolling_max

        # Market average 3-month return
        mkt_ret_3m = ret_3m.mean(axis=1)

        # 9 signals (each 0 or 1)
        s1 = (ret_12m > 0).astype(float)
        s2 = (ret_1m > 0).astype(float)
        s3 = (ret_12m > ret_6m).astype(float)
        s4 = (vol_12m < vol_12m.median(axis=1).values[:, None]).astype(float)
        s5 = (vol_6m < vol_12m).astype(float)
        s6 = (prices > sma_200).astype(float)
        s7 = (ret_3m > 0).astype(float)
        s8 = ret_3m.gt(mkt_ret_3m, axis=0).astype(float)
        s9 = (drawdown > drawdown.median(axis=1).values[:, None]).astype(float)

        fscore = s1 + s2 + s3 + s4 + s5 + s6 + s7 + s8 + s9

        ranks = fscore.rank(axis=1, method="average", ascending=True)
        rank_mean = ranks.mean(axis=1)
        demeaned = ranks.sub(rank_mean, axis=0)
        abs_sum = demeaned.abs().sum(axis=1).replace(0.0, np.nan)
        weights = demeaned.div(abs_sum, axis=0)

        if self.long_only:
            weights = weights.clip(lower=0.0)
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
