"""Simple moving-average crossover, 10/30.

Paper
-----
Brock, W., Lakonishok, J. & LeBaron, B. (1992).
*Simple technical trading rules and the stochastic properties of
stock returns*. The Journal of Finance, 47(5), 1731–1764.
https://doi.org/10.1111/j.1540-6261.1992.tb04681.x

BLL (1992) test a handful of moving-average variable-length moving-
average (VMA) rules against a bootstrap null and show that the
classic fast-over-slow SMA crossover produces statistically
significant positive returns on the Dow Jones from 1897–1986. The
10/30 pair is one of their canonical configurations.

Rules
-----
For each asset independently:

* Long  when ``SMA(fast) > SMA(slow)``
* Short when ``SMA(fast) < SMA(slow)``
* Flat  on the rebalance day when fast == slow
* ``long_only=True`` collapses shorts into flat

Portfolio
---------
Each asset contributes ``sign(fast − slow) / n_symbols`` to the
portfolio weight. When every asset in the universe is aligned long,
the gross book is 1.0; when mixed, the gross book is smaller.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class SMACross1030:
    """10/30 simple moving average crossover (BLL 1992)."""

    name: str = "sma_cross_10_30"
    family: str = "trend"
    asset_classes: tuple[str, ...] = ("equity", "future", "fx", "commodity", "crypto")
    paper_doi: str = "10.1111/j.1540-6261.1992.tb04681.x"
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        fast_window: int = 10,
        slow_window: int = 30,
        long_only: bool = False,
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
