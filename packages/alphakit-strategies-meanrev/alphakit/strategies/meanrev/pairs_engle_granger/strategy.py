"""Engle-Granger cointegration pairs trading (Engle & Granger 1987).

Reference
---------
Engle, R.F. & Granger, C.W.J. (1987). Co-Integration and Error
Correction: Representation, Estimation, and Testing. *Econometrica*,
55(2), 251-276. DOI: 10.2307/1913236.

The Engle-Granger method tests for cointegration between two price
series by regressing one on the other and testing the residual for
stationarity. If cointegrated, the residual is mean-reverting and
can be traded as a spread.

This implementation uses rolling OLS to estimate the hedge ratio
and trades the Z-score of the resulting spread.

Rules
-----
For each pair (i, j):
  1. Rolling OLS: price_i = alpha + beta * price_j + epsilon
  2. Spread = price_i − beta * price_j
  3. Z-score of spread
  4. Trade spread mean reversion at ±threshold
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class PairsEngleGranger:
    """Engle-Granger cointegration pairs — 1-year rolling hedge ratio."""

    name: str = "pairs_engle_granger"
    family: str = "meanrev"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.2307/1913236"  # Engle & Granger (1987)
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

    def _rolling_beta(self, y: np.ndarray, x: np.ndarray, window: int) -> np.ndarray:
        """Rolling OLS beta: y = alpha + beta * x."""
        n = len(y)
        beta = np.full(n, np.nan)
        for t in range(window, n):
            x_w = x[t - window : t]
            y_w = y[t - window : t]
            x_mean = x_w.mean()
            y_mean = y_w.mean()
            ss_xx = float(np.sum((x_w - x_mean) ** 2))
            if ss_xx < 1e-15:
                continue
            ss_xy = float(np.sum((x_w - x_mean) * (y_w - y_mean)))
            beta[t] = ss_xy / ss_xx
        return beta

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
                beta = self._rolling_beta(price_np[:, i], price_np[:, j], self.formation_period)
                spread = price_np[:, i] - beta * price_np[:, j]

                # Z-score of spread
                spread_series = pd.Series(spread, index=prices.index)
                s_mean = spread_series.rolling(
                    window=self.zscore_lookback, min_periods=self.zscore_lookback
                ).mean()
                s_std = spread_series.rolling(
                    window=self.zscore_lookback, min_periods=self.zscore_lookback
                ).std(ddof=1)
                zscore = ((spread_series - s_mean) / s_std.replace(0.0, np.nan)).to_numpy()

                sig_i = np.where(
                    zscore >= self.threshold,
                    -1.0,
                    np.where(zscore <= -self.threshold, 1.0, 0.0),
                )
                sig_j = -sig_i * np.where(np.isnan(beta), 0.0, beta)

                weights.iloc[:, i] += np.nan_to_num(sig_i, nan=0.0)
                weights.iloc[:, j] += np.nan_to_num(sig_j, nan=0.0)

        abs_sum = weights.abs().sum(axis=1).replace(0.0, np.nan)
        weights = weights.div(abs_sum, axis=0)

        if self.long_only:
            weights = weights.clip(lower=0.0)
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
