"""Kalman-filtered dynamic hedge ratio pairs trading (Chan 2013).

Reference
---------
Chan, E.P. (2013). *Algorithmic Trading: Winning Strategies and
Their Rationale*. Wiley. ISBN 978-1-118-46014-6.

A Kalman filter provides a dynamic, online estimate of the hedge
ratio between two cointegrated assets. Unlike a rolling OLS window,
the Kalman filter smoothly adapts to regime changes and provides
a principled way to update beliefs about the hedge ratio.

Rules
-----
For each pair (i, j):
  1. Kalman filter: price_i = beta * price_j + epsilon
  2. Spread = price_i − beta_kalman * price_j
  3. Z-score of spread residual
  4. Trade when Z-score exceeds ±threshold
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class PairsKalman:
    """Kalman-filtered dynamic hedge ratio pairs trading."""

    name: str = "pairs_kalman"
    family: str = "meanrev"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "978-1-118-46014-6"  # Chan (2013)
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        delta: float = 1e-4,
        ve: float = 1e-3,
        zscore_lookback: int = 20,
        threshold: float = 2.0,
        long_only: bool = False,
    ) -> None:
        if delta <= 0.0:
            raise ValueError(f"delta must be positive, got {delta}")
        if ve <= 0.0:
            raise ValueError(f"ve must be positive, got {ve}")
        if zscore_lookback <= 1:
            raise ValueError(f"zscore_lookback must be > 1, got {zscore_lookback}")
        if threshold <= 0.0:
            raise ValueError(f"threshold must be positive, got {threshold}")
        self.delta = delta
        self.ve = ve
        self.zscore_lookback = zscore_lookback
        self.threshold = threshold
        self.long_only = long_only

    def _kalman_hedge(self, y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Scalar Kalman filter for hedge ratio: y = beta * x + eps.

        Returns (beta_series, spread_series).
        """
        n = len(y)
        beta = np.zeros(n)
        spread = np.zeros(n)

        # State: beta (scalar), covariance: R (scalar)
        b = 0.0  # initial beta estimate
        r = 1.0  # initial uncertainty

        for t in range(n):
            # Prediction
            r_pred = r + self.delta

            # Observation
            x_t = x[t]
            y_pred = b * x_t
            e = y[t] - y_pred  # innovation

            # Kalman gain
            s = x_t * r_pred * x_t + self.ve
            if abs(s) < 1e-15:
                beta[t] = b
                spread[t] = e
                continue
            k = r_pred * x_t / s

            # Update
            b = b + k * e
            r = (1.0 - k * x_t) * r_pred

            beta[t] = b
            spread[t] = e

        return beta, spread

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

        weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        price_np = prices.to_numpy()

        for i in range(n_assets):
            for j in range(i + 1, n_assets):
                beta, spread = self._kalman_hedge(price_np[:, i], price_np[:, j])

                spread_s = pd.Series(spread, index=prices.index)
                s_mean = spread_s.rolling(
                    window=self.zscore_lookback, min_periods=self.zscore_lookback
                ).mean()
                s_std = spread_s.rolling(
                    window=self.zscore_lookback, min_periods=self.zscore_lookback
                ).std(ddof=1)
                zscore = ((spread_s - s_mean) / s_std.replace(0.0, np.nan)).to_numpy()

                sig_i = np.where(
                    zscore >= self.threshold,
                    -1.0,
                    np.where(zscore <= -self.threshold, 1.0, 0.0),
                )
                sig_j = -sig_i * beta

                weights.iloc[:, i] += np.nan_to_num(sig_i, nan=0.0)
                weights.iloc[:, j] += np.nan_to_num(sig_j, nan=0.0)

        abs_sum = weights.abs().sum(axis=1).replace(0.0, np.nan)
        weights = weights.div(abs_sum, axis=0)

        if self.long_only:
            weights = weights.clip(lower=0.0)
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
