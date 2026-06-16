"""Golden-cross SMA(50)/SMA(200).

Paper
-----
Brock, W., Lakonishok, J. & LeBaron, B. (1992). *Simple technical
trading rules and the stochastic properties of stock returns*.
The Journal of Finance, 47(5), 1731–1764.
https://doi.org/10.1111/j.1540-6261.1992.tb04681.x

The 50/200 crossover is the single most widely-watched technical signal
on Wall Street: a "golden cross" when SMA(50) crosses above SMA(200), a
"death cross" when it crosses below. BLL (1992) test a 50/200 variant
as one of their headline rules and find statistically significant
positive excess returns on the Dow Jones from 1897–1986 before
transaction costs.

Per-asset weights are ``sign(fast − slow) / n_symbols``, same
convention as ``sma_cross_10_30``. Long-only mode collapses shorts
into flat (many practitioners use the 50/200 cross as a binary
equity-exposure switch rather than a long/short signal).
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class SMACross50200:
    """Golden-cross SMA(50)/SMA(200)."""

    name: str = "sma_cross_50_200"
    family: str = "trend"
    asset_classes: tuple[str, ...] = ("equity", "future", "fx", "commodity", "crypto")
    paper_doi: str = "10.1111/j.1540-6261.1992.tb04681.x"
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        fast_window: int = 50,
        slow_window: int = 200,
        long_only: bool = True,
    ) -> None:
        if fast_window <= 0:
            raise ValueError(f"fast_window must be positive, got {fast_window}")
        if slow_window <= 0:
            raise ValueError(f"slow_window must be positive, got {slow_window}")
        if fast_window >= slow_window:
            raise ValueError(f"fast_window ({fast_window}) must be < slow_window ({slow_window})")
        self.fast_window = fast_window
        self.slow_window = slow_window
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

        fast_sma = prices.rolling(self.fast_window, min_periods=self.fast_window).mean()
        slow_sma = prices.rolling(self.slow_window, min_periods=self.slow_window).mean()

        signal_np = np.sign((fast_sma - slow_sma).to_numpy())
        signal = pd.DataFrame(signal_np, index=prices.index, columns=prices.columns)

        if self.long_only:
            signal = signal.clip(lower=0.0)

        n = len(prices.columns)
        weights = signal / n
        return cast(pd.DataFrame, weights.fillna(0.0))
