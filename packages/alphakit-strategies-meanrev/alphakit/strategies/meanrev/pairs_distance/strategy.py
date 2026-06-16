"""Distance-method pairs trading (Gatev, Goetzmann & Rouwenhorst 2006).

Reference
---------
Gatev, E., Goetzmann, W.N. & Rouwenhorst, K.G. (2006). Pairs
Trading: Performance of a Relative-Value Arbitrage Rule. *Review
of Financial Studies*, 19(3), 797-827. DOI: 10.1093/rfs/hhj020.

The GGR distance method forms pairs by minimizing the sum of
squared deviations between normalized price series over a formation
period. During the trading period, when the spread between a pair
exceeds a threshold, the strategy goes long the underperformer and
short the outperformer.

This implementation uses a simplified version: for each pair of
assets in the universe, compute the normalized spread and trade
when the Z-score of the spread exceeds ±threshold.

Rules
-----
For each pair (i, j):
  1. Normalize prices to start at 1.0 over formation window
  2. Spread = normalized_i − normalized_j
  3. Z-score of spread
  4. If Z > threshold: short i, long j
  5. If Z < −threshold: long i, short j
  6. Aggregate across all pairs, normalize
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class PairsDistance:
    """GGR distance-method pairs trading — top-N closest pairs."""

    name: str = "pairs_distance"
    family: str = "meanrev"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1093/rfs/hhj020"  # Gatev, Goetzmann & Rouwenhorst (2006)
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        formation_period: int = 252,
        zscore_lookback: int = 20,
        threshold: float = 2.0,
        long_only: bool = False,
    ) -> None:
        if formation_period <= 1:
            raise ValueError(f"formation_period must be > 1, got {formation_period}")
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

        weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

        # Normalize prices by rolling formation-period start
        log_p = pd.DataFrame(np.log(prices.to_numpy()), index=prices.index, columns=prices.columns)
        norm = (
            log_p
            - log_p.rolling(window=self.formation_period, min_periods=self.formation_period).mean()
        )

        for i in range(n_assets):
            for j in range(i + 1, n_assets):
                spread = norm.iloc[:, i] - norm.iloc[:, j]
                spread_mean = spread.rolling(
                    window=self.zscore_lookback, min_periods=self.zscore_lookback
                ).mean()
                spread_std = spread.rolling(
                    window=self.zscore_lookback, min_periods=self.zscore_lookback
                ).std(ddof=1)
                zscore = (spread - spread_mean) / spread_std.replace(0.0, np.nan)

                z_np = zscore.to_numpy()
                # Spread too high → short i, long j
                sig_i = np.where(
                    z_np >= self.threshold, -1.0, np.where(z_np <= -self.threshold, 1.0, 0.0)
                )
                sig_j = -sig_i

                weights.iloc[:, i] += sig_i
                weights.iloc[:, j] += sig_j

        # Normalize weights
        abs_sum = weights.abs().sum(axis=1).replace(0.0, np.nan)
        weights = weights.div(abs_sum, axis=0)

        if self.long_only:
            weights = weights.clip(lower=0.0)
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
