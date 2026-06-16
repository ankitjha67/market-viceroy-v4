"""Yield-curve PCA trade — mean-reversion of idiosyncratic residual after top-3 PCs.

Implementation notes
====================

Foundational and primary paper
------------------------------
Litterman, R. & Scheinkman, J. (1991).
*Common factors affecting bond returns*. Journal of Fixed Income,
1(1), 54–61.
DOI: 10.3905/jfi.1991.692347

Litterman/Scheinkman decompose the yield curve into three principal
components — level (PC1, ~80% of variance), slope (PC2, ~15%), and
curvature (PC3, ~5%). Anything explained by these three factors is
*priced risk*; anything *unexplained* is the idiosyncratic noise on
each bond, which is mean-reverting around zero.

This strategy isolates the unexplained residual: at each rolling
window, fit PCA on bond returns, project the most recent monthly
return onto the top 3 PCs, compute the residual, accumulate the
residual over a recent window, z-score it across bonds, and take
mean-reversion positions.

Why a single citation
---------------------
The mean-reversion-on-PCA-residual rule is fully specified by the
Litterman/Scheinkman PCA framework — once you accept that the top
3 PCs capture priced risk and the residual is idiosyncratic, the
trading rule follows mechanically. No separate expected-return
paper is needed.

Differentiation from `curve_butterfly_2s5s10s`
----------------------------------------------
* `curve_butterfly_2s5s10s` — fixed-weight ½/−1/½ proxy for PC3 on
  a specific 2-5-10Y triplet. Simpler and more deterministic.
* `yield_curve_pca_trade` (this strategy) — full rolling PCA fit on
  an N-bond panel, trades the residual *after* the top 3 PCs. The
  signal isolates strictly idiosyncratic deviation per bond.

Both strategies trade Litterman/Scheinkman-style residuals but on
different signal scales: the butterfly is a single-trade instrument
on the fitted curvature; the PCA trade is a cross-sectional rank on
all bonds simultaneously after stripping the top 3 PCs. Expected ρ
between the two ≈ 0.6-0.8 — they are partial overlaps, not
duplicates.

Algorithm
---------
For each month-end ``t`` in the daily index:

1. Take a trailing window of monthly log returns over
   ``pca_window_months`` months, shape ``(window, n_assets)``.
2. De-mean the window column-wise (subtract per-asset mean over
   the window).
3. Compute the covariance matrix of the de-meaned returns.
4. Eigendecompose: ``eigvals, eigvecs = np.linalg.eigh(cov)``.
   Take the top ``n_pcs`` eigenvectors (the columns corresponding
   to the largest eigenvalues).
5. **Reconstruct** the most recent monthly return from the top PCs::

       scores = top_eigvecs.T @ current_return   # shape (n_pcs,)
       reconstructed = top_eigvecs @ scores       # shape (n_assets,)

6. **Residual:** ``residual = current_return − reconstructed``.
7. **Cross-sectional rank** of residuals → dollar-neutral mean-
   reversion weights::

       weight_i = −sign(residual_i) × |residual_rank_i| / Σ|residual_rank_k|

   (Negative sign: short the bond with positive residual, long the
   bond with negative residual.)

8. Forward-fill weights to daily until the next month-end.

Edge cases
----------
* Before ``pca_window_months`` of monthly data are available, weights
  are zero.
* If ``n_pcs >= n_assets``, the residual is identically zero and
  weights are zero. The strategy enforces ``n_pcs < n_assets`` at
  construction.
* Constant prices in any bond zero out its variance contribution;
  the PCA still runs but that bond's residual is zero.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class YieldCurvePCATrade:
    """Cross-sectional mean-reversion on PCA residuals after top-3 yield-curve factors.

    Parameters
    ----------
    n_pcs
        Number of top principal components to project onto. Defaults
        to ``3`` (level, slope, curvature). Must be strictly less
        than the number of bond columns in the input.
    pca_window_months
        Trailing window (in months) for the rolling covariance fit.
        Defaults to ``24`` (2 years), which gives enough degrees of
        freedom for a stable PCA fit while remaining reactive to
        regime change.
    residual_lookback_months
        How many months of trailing residuals to accumulate before
        ranking. Defaults to ``3`` — Durham-style short lookback to
        avoid stale residuals dominating the rank.
    """

    name: str = "yield_curve_pca_trade"
    family: str = "rates"
    asset_classes: tuple[str, ...] = ("bond",)
    paper_doi: str = "10.3905/jfi.1991.692347"  # Litterman/Scheinkman 1991
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        n_pcs: int = 3,
        pca_window_months: int = 24,
        residual_lookback_months: int = 3,
    ) -> None:
        if n_pcs < 1:
            raise ValueError(f"n_pcs must be >= 1, got {n_pcs}")
        if pca_window_months < 12:
            raise ValueError(f"pca_window_months must be >= 12, got {pca_window_months}")
        if residual_lookback_months < 1:
            raise ValueError(
                f"residual_lookback_months must be >= 1, got {residual_lookback_months}"
            )
        if residual_lookback_months > pca_window_months:
            raise ValueError(
                f"residual_lookback_months ({residual_lookback_months}) must be <= "
                f"pca_window_months ({pca_window_months})"
            )

        self.n_pcs = n_pcs
        self.pca_window_months = pca_window_months
        self.residual_lookback_months = residual_lookback_months

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return dollar-neutral PCA-residual mean-reversion weights.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps with N >= n_pcs+1
            bond proxy columns.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if prices.shape[1] <= self.n_pcs:
            raise ValueError(
                f"prices must have > n_pcs ({self.n_pcs}) columns; got {prices.shape[1]}"
            )
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        month_end_prices = prices.resample("ME").last()
        monthly_returns = np.log(month_end_prices / month_end_prices.shift(1))
        n_months = len(monthly_returns)
        n_assets = monthly_returns.shape[1]

        residuals = pd.DataFrame(0.0, index=monthly_returns.index, columns=monthly_returns.columns)

        for i in range(self.pca_window_months, n_months):
            window = monthly_returns.iloc[i - self.pca_window_months : i].dropna(how="any")
            if len(window) < self.pca_window_months // 2:
                continue
            window_arr = window.to_numpy()
            window_demeaned = window_arr - window_arr.mean(axis=0, keepdims=True)
            cov = (window_demeaned.T @ window_demeaned) / (len(window_arr) - 1)
            _eigvals, eigvecs = np.linalg.eigh(cov)
            top_eigvecs = eigvecs[:, -self.n_pcs :]

            current_return = monthly_returns.iloc[i].to_numpy()
            if np.isnan(current_return).any():
                continue
            current_demeaned = current_return - window_arr.mean(axis=0)
            scores = top_eigvecs.T @ current_demeaned
            reconstructed = top_eigvecs @ scores
            residual = current_demeaned - reconstructed
            residuals.iloc[i] = residual

        rolling_residual = residuals.rolling(self.residual_lookback_months).sum()

        ranks = rolling_residual.rank(axis=1, method="average", ascending=False)
        n = float(n_assets)
        demeaned_rank = ranks - (n + 1.0) / 2.0
        weights = -demeaned_rank
        normaliser = weights.abs().sum(axis=1).replace(0.0, np.nan)
        monthly_weights = weights.div(normaliser, axis=0)

        daily_weights = monthly_weights.reindex(prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights)
