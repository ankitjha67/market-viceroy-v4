"""Crypto funding rate carry (no formal DOI — crypto-native).

Reference
---------
No formal academic citation. The perpetual funding rate mechanism
is documented in Binance, Deribit, and other exchange documentation.

When the perp funding rate is positive, longs pay shorts — indicating
bullish positioning and a premium. A carry strategy collects this
premium by going short perp + long spot. When funding is negative,
the strategy reverses.

**Phase 1 proxy**: Without actual funding rate data, this
implementation uses the fast/slow MA spread as a funding proxy
(same approach as crypto_basis_perp in the meanrev family).
Positive basis proxy → funding likely positive → short exposure.
Negative basis proxy → funding likely negative → long exposure.

Rules
-----
For each asset:
  1. Fast MA and slow MA of prices
  2. Funding proxy = (fast MA − slow MA) / slow MA
  3. If funding proxy > threshold: short (collect positive funding)
  4. If funding proxy < −threshold: long (collect negative funding)
  5. Otherwise flat
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class CryptoFundingCarry:
    """Crypto funding rate carry — collect perp funding premium."""

    name: str = "crypto_funding_carry"
    family: str = "carry"
    asset_classes: tuple[str, ...] = ("crypto",)
    paper_doi: str = "crypto-native-no-formal-doi"
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        fast_period: int = 5,
        slow_period: int = 30,
        threshold: float = 0.005,
        long_only: bool = False,
    ) -> None:
        if fast_period <= 0:
            raise ValueError(f"fast_period must be positive, got {fast_period}")
        if slow_period <= 0:
            raise ValueError(f"slow_period must be positive, got {slow_period}")
        if fast_period >= slow_period:
            raise ValueError(f"fast_period ({fast_period}) must be < slow_period ({slow_period})")
        if threshold <= 0.0:
            raise ValueError(f"threshold must be positive, got {threshold}")
        self.fast_period = fast_period
        self.slow_period = slow_period
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

        fast_ma = prices.rolling(window=self.fast_period, min_periods=self.fast_period).mean()
        slow_ma = prices.rolling(window=self.slow_period, min_periods=self.slow_period).mean()

        # Funding proxy: relative premium of fast over slow
        funding_proxy = (fast_ma - slow_ma) / slow_ma.replace(0.0, np.nan)

        f_np = funding_proxy.to_numpy()
        # Positive funding → short to collect; negative → long to collect
        signal = pd.DataFrame(
            np.where(
                f_np >= self.threshold,
                -1.0,
                np.where(f_np <= -self.threshold, 1.0, 0.0),
            ),
            index=prices.index,
            columns=prices.columns,
        )

        if self.long_only:
            signal = signal.clip(lower=0.0)

        n = len(prices.columns)
        weights = signal / n
        return cast(pd.DataFrame, weights.fillna(0.0))
