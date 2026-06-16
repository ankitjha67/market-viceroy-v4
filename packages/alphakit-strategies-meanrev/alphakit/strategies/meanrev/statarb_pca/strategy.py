"""Avellaneda-Lee PCA residual statistical arbitrage (Avellaneda & Lee 2010).

Reference
---------
Avellaneda, M. & Lee, J.-H. (2010). Statistical Arbitrage in the
US Equities Market. *Quantitative Finance*, 10(7), 761-782.
DOI: 10.1080/14697680902743953.

The PCA stat arb strategy decomposes asset returns into systematic
(factor) and idiosyncratic (residual) components using PCA. The
residuals are modeled as OU processes and traded when they diverge
significantly from zero.

This implementation uses a rolling PCA to extract N_factors principal
components, computes the residual for each asset, and trades the
Z-score of the cumulative residual.

Rules
-----
  1. Rolling PCA on return covariance → factor loadings
  2. Residual_i = return_i − sum(loading_ij * factor_j)
  3. Cumulative residual (OU-like process)
  4. Z-score of cumulative residual
  5. Trade mean reversion at ±threshold
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class StatArbPCA:
    """Avellaneda-Lee PCA residual stat arb — 15-factor decomposition."""

    name: str = "statarb_pca"
    family: str = "meanrev"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1080/14697680902743953"  # Avellaneda & Lee (2010)
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        n_factors: int = 15,
        formation_period: int = 252,
        zscore_lookback: int = 20,
        threshold: float = 2.0,
        long_only: bool = False,
    ) -> None:
        if n_factors <= 0:
            raise ValueError(f"n_factors must be positive, got {n_factors}")
        if formation_period <= 2:
            raise ValueError(f"formation_period must be > 2, got {formation_period}")
        if zscore_lookback <= 1:
            raise ValueError(f"zscore_lookback must be > 1, got {zscore_lookback}")
        if threshold <= 0.0:
            raise ValueError(f"threshold must be positive, got {threshold}")
        self.n_factors = n_factors
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

        # Cap factors at n_assets - 1
        k = min(self.n_factors, n_assets - 1)

        returns = prices.pct_change().to_numpy()
        n_rows = len(prices)
        warmup = self.formation_period + self.zscore_lookback + 1

        # Compute rolling residuals
        cum_residual = np.zeros((n_rows, n_assets))

        for t in range(self.formation_period + 1, n_rows):
            ret_window = returns[t - self.formation_period : t]

            # Remove NaN rows (first row of returns)
            valid = ~np.any(np.isnan(ret_window), axis=1)
            ret_clean = ret_window[valid]
            if len(ret_clean) < k + 2:
                continue

            # PCA via SVD
            ret_centered = ret_clean - ret_clean.mean(axis=0)
            try:
                _, _s, vt = np.linalg.svd(ret_centered, full_matrices=False)
            except np.linalg.LinAlgError:
                continue

            # Top k factors
            factors = vt[:k]  # shape: (k, n_assets)

            # Current return
            r_t = returns[t]
            if np.any(np.isnan(r_t)):
                continue

            # Project return onto factors
            loadings = factors @ r_t  # shape: (k,)
            systematic = loadings @ factors  # shape: (n_assets,)
            residual = r_t - systematic

            # Cumulative residual with decay (OU-like)
            cum_residual[t] = 0.95 * cum_residual[t - 1] + residual

        # Z-score of cumulative residuals per asset
        weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

        for col_idx in range(n_assets):
            resid_s = pd.Series(cum_residual[:, col_idx], index=prices.index)
            r_mean = resid_s.rolling(
                window=self.zscore_lookback, min_periods=self.zscore_lookback
            ).mean()
            r_std = resid_s.rolling(
                window=self.zscore_lookback, min_periods=self.zscore_lookback
            ).std(ddof=1)
            zscore = ((resid_s - r_mean) / r_std.replace(0.0, np.nan)).to_numpy()

            for t in range(warmup, n_rows):
                z = zscore[t]
                if np.isnan(z):
                    continue
                if z >= self.threshold:
                    weights.iat[t, col_idx] = -1.0 / n_assets
                elif z <= -self.threshold:
                    weights.iat[t, col_idx] = 1.0 / n_assets

        if self.long_only:
            weights = weights.clip(lower=0.0)

        return weights
