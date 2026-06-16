"""Perpetual-spot basis mean reversion — crypto-native.

Reference
---------
No formal academic citation. The perp-spot basis (funding rate
arbitrage) is a well-documented crypto-native phenomenon: when the
perpetual futures price trades at a premium to spot, longs pay
shorts via the funding rate. This premium tends to mean-revert.

This implementation proxies the basis via the rolling Z-score of
the spread between two price series (e.g. perp vs spot). In a
single-price-series context, it uses the deviation of short-term
momentum from long-term momentum as a basis proxy.

Rules
-----
For each asset:
  1. Compute fast MA and slow MA of prices
  2. Basis proxy = (fast MA − slow MA) / slow MA
  3. Z-score of basis proxy over rolling window
  4. Short when Z > threshold (premium too high, expect convergence)
  5. Long when Z < −threshold (discount, expect convergence)
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class CryptoBasisPerp:
    """Perp-spot basis mean reversion — fade extreme funding premiums."""

    name: str = "crypto_basis_perp"
    family: str = "meanrev"
    asset_classes: tuple[str, ...] = ("crypto",)
    paper_doi: str = "crypto-native-no-formal-doi"
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        fast_period: int = 5,
        slow_period: int = 30,
        zscore_lookback: int = 20,
        threshold: float = 2.0,
        long_only: bool = False,
    ) -> None:
        if fast_period <= 0:
            raise ValueError(f"fast_period must be positive, got {fast_period}")
        if slow_period <= 0:
            raise ValueError(f"slow_period must be positive, got {slow_period}")
        if fast_period >= slow_period:
            raise ValueError(f"fast_period ({fast_period}) must be < slow_period ({slow_period})")
        if zscore_lookback <= 1:
            raise ValueError(f"zscore_lookback must be > 1, got {zscore_lookback}")
        if threshold <= 0.0:
            raise ValueError(f"threshold must be positive, got {threshold}")
        self.fast_period = fast_period
        self.slow_period = slow_period
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

        warmup = self.slow_period + self.zscore_lookback

        fast_ma = prices.rolling(window=self.fast_period, min_periods=self.fast_period).mean()
        slow_ma = prices.rolling(window=self.slow_period, min_periods=self.slow_period).mean()

        # Basis proxy: relative premium of fast over slow
        basis = (fast_ma - slow_ma) / slow_ma.replace(0.0, np.nan)

        # Z-score of basis
        basis_mean = basis.rolling(
            window=self.zscore_lookback, min_periods=self.zscore_lookback
        ).mean()
        basis_std = basis.rolling(
            window=self.zscore_lookback, min_periods=self.zscore_lookback
        ).std(ddof=1)
        basis_z = (basis - basis_mean) / basis_std.replace(0.0, np.nan)

        z_np = basis_z.to_numpy()
        # Fade the premium: short when basis is too high, long when too low
        signal = pd.DataFrame(
            np.where(
                z_np <= -self.threshold,
                1.0,
                np.where(z_np >= self.threshold, -1.0, 0.0),
            ),
            index=prices.index,
            columns=prices.columns,
        )

        if self.long_only:
            signal = signal.clip(lower=0.0)

        n = len(prices.columns)
        weights = signal / n

        # Enforce warmup
        result = weights.fillna(0.0)
        result.iloc[:warmup] = 0.0

        return cast(pd.DataFrame, result)
