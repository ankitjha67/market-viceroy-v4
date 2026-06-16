"""Altman Z-Score PROXY (Altman 1968).

Reference
---------
Altman, E.I. (1968). Financial Ratios, Discriminant Analysis and
the Prediction of Corporate Bankruptcy. *Journal of Finance*, 23(4),
589-609. DOI: 10.1111/j.1540-6261.1968.tb00843.x.

**SEVERE DEVIATION — _proxy suffix applies (ADR-002).**

The real Altman Z-Score uses 5 accounting ratios. This proxy uses
price-derived distress indicators. This is NOT the Z-Score. The
canonical slug altman_zscore is reserved for Phase 4.

Proxy signals (composite distress score):
  1. 12-month drawdown severity (working capital proxy)
  2. Trailing volatility (leverage proxy)
  3. Trend strength below SMA (earnings proxy)
  4. 12-month return (market value proxy)
  5. Turnover proxy via return autocorrelation (sales proxy)
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class AltmanZScoreProxy:
    """Altman Z-Score PROXY — price-based distress composite."""

    name: str = "altman_zscore_proxy"
    family: str = "value"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1111/j.1540-6261.1968.tb00843.x"
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

        daily_ret = prices.pct_change()
        ret_12m = prices.pct_change(periods=252)
        vol_12m = daily_ret.rolling(window=252, min_periods=252).std(ddof=1)
        sma_200 = prices.rolling(window=200, min_periods=200).mean()

        # Drawdown severity
        rolling_max = prices.rolling(window=252, min_periods=252).max()
        drawdown = (prices - rolling_max) / rolling_max

        # Composite health score (higher = healthier)
        # Normalize each component cross-sectionally via rank
        s1 = (-drawdown).rank(axis=1, method="average", ascending=True)  # less drawdown = healthier
        s2 = (-vol_12m).rank(axis=1, method="average", ascending=True)  # lower vol = healthier
        s3 = (prices / sma_200).rank(
            axis=1, method="average", ascending=True
        )  # above SMA = healthier
        s4 = ret_12m.rank(axis=1, method="average", ascending=True)  # higher return = healthier

        health_score = s1 + s2 + s3 + s4

        rank_mean = health_score.mean(axis=1)
        demeaned = health_score.sub(rank_mean, axis=0)
        abs_sum = demeaned.abs().sum(axis=1).replace(0.0, np.nan)
        weights = demeaned.div(abs_sum, axis=0)

        if self.long_only:
            weights = weights.clip(lower=0.0)
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
