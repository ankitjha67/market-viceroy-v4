"""Johansen multi-asset cointegration (Johansen 1991).

Reference
---------
Johansen, S. (1991). Estimation and Hypothesis Testing of
Cointegration Vectors in Gaussian Vector Autoregressive Models.
*Econometrica*, 59(6), 1551-1580. DOI: 10.2307/2938278.

The Johansen procedure extends Engle-Granger to N > 2 assets by
finding cointegrating vectors via eigendecomposition of a VECM
(Vector Error Correction Model). This gives the linear combination
of assets that is most stationary.

This implementation uses a simplified approach: compute the first
principal component of rolling log-price differences, use it as the
cointegrating vector, and trade the resulting spread.

Rules
-----
  1. Rolling window of log-prices
  2. Compute first eigenvector of the covariance of price changes
  3. Spread = eigenvector · log_prices
  4. Z-score of spread
  5. Trade mean reversion at ±threshold
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class PairsJohansen:
    """Johansen multi-asset cointegration — eigendecomposition spread."""

    name: str = "pairs_johansen"
    family: str = "meanrev"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.2307/2938278"  # Johansen (1991)
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        formation_period: int = 252,
        zscore_lookback: int = 20,
        threshold: float = 2.0,
        long_only: bool = False,
    ) -> None:
        if formation_period <= 2:
            raise ValueError(f"formation_period must be > 2, got {formation_period}")
        if zscore_lookback <= 1:
            raise ValueError(f"zscore_lookback must be > 1, got {zscore_lookback}")
        if threshold <= 0.0:
            raise ValueError(f"threshold must be positive, got {threshold}")
        self.formation_period = formation_period
        self.zscore_lookback = zscore_lookback
        self.threshold = threshold
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

        n_rows = len(prices)
        log_p = np.log(prices.to_numpy())
        weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        warmup = self.formation_period + self.zscore_lookback

        # Compute rolling cointegrating vector and spread
        spread_arr = np.full(n_rows, np.nan)
        eigvec_arr = np.full((n_rows, n_assets), np.nan)

        for t in range(self.formation_period, n_rows):
            window = log_p[t - self.formation_period : t]
            diffs = np.diff(window, axis=0)
            cov = np.cov(diffs, rowvar=False)
            if cov.ndim < 2:
                continue
            try:
                _eigenvalues, eigenvectors = np.linalg.eigh(cov)
            except np.linalg.LinAlgError:
                continue
            # First eigenvector (smallest eigenvalue = most stationary)
            vec = eigenvectors[:, 0]
            # Normalize so that sum of absolute values = 1
            norm = np.sum(np.abs(vec))
            if norm < 1e-15:
                continue
            vec = vec / norm
            eigvec_arr[t] = vec
            spread_arr[t] = float(vec @ log_p[t])

        # Z-score of spread
        spread_s = pd.Series(spread_arr, index=prices.index)
        s_mean = spread_s.rolling(
            window=self.zscore_lookback, min_periods=self.zscore_lookback
        ).mean()
        s_std = spread_s.rolling(window=self.zscore_lookback, min_periods=self.zscore_lookback).std(
            ddof=1
        )
        zscore = ((spread_s - s_mean) / s_std.replace(0.0, np.nan)).to_numpy()

        for t in range(warmup, n_rows):
            z = zscore[t]
            if np.isnan(z):
                continue
            vec = eigvec_arr[t]
            if np.any(np.isnan(vec)):
                continue

            if z >= self.threshold:
                weights.iloc[t] = -vec  # spread too high → sell spread
            elif z <= -self.threshold:
                weights.iloc[t] = vec  # spread too low → buy spread

        # Normalize to bounded weights
        abs_sum = weights.abs().sum(axis=1).replace(0.0, np.nan)
        weights = weights.div(abs_sum, axis=0)

        if self.long_only:
            weights = weights.clip(lower=0.0)
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
