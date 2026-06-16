"""EMA 12/26 crossover (Appel's MACD trigger).

Book
----
Appel, G. (2005). *Technical Analysis: Power Tools for Active
Investors*. Financial Times Prentice Hall. ISBN 978-0131479029.

Appel's MACD (Moving Average Convergence/Divergence) indicator uses
the difference between the 12-period and 26-period EMAs as its
primary signal line. A long signal fires when EMA(12) crosses above
EMA(26); a short signal when it crosses below. This strategy ships
the naked EMA cross (no signal-line smoothing) because the smoothed
signal-line cross lives in `ema_cross_macd_signal` (Phase 4).

Rules
-----
For each asset independently, weight = ``sign(EMA(12) − EMA(26)) /
n_symbols``. Same multi-asset convention as `sma_cross_10_30`.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class EMACross1226:
    """Appel MACD trigger — 12/26 EMA crossover."""

    name: str = "ema_cross_12_26"
    family: str = "trend"
    asset_classes: tuple[str, ...] = ("equity", "future", "fx", "commodity", "crypto")
    paper_doi: str = "978-0131479029"  # ISBN of Appel (2005)
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        fast_span: int = 12,
        slow_span: int = 26,
        long_only: bool = False,
    ) -> None:
        if fast_span <= 0:
            raise ValueError(f"fast_span must be positive, got {fast_span}")
        if slow_span <= 0:
            raise ValueError(f"slow_span must be positive, got {slow_span}")
        if fast_span >= slow_span:
            raise ValueError(f"fast_span ({fast_span}) must be < slow_span ({slow_span})")
        self.fast_span = fast_span
        self.slow_span = slow_span
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

        fast_ema = prices.ewm(span=self.fast_span, adjust=False, min_periods=self.slow_span).mean()
        slow_ema = prices.ewm(span=self.slow_span, adjust=False, min_periods=self.slow_span).mean()

        signal_np = np.sign((fast_ema - slow_ema).to_numpy())
        signal = pd.DataFrame(signal_np, index=prices.index, columns=prices.columns)

        if self.long_only:
            signal = signal.clip(lower=0.0)

        n = len(prices.columns)
        weights = signal / n
        return cast(pd.DataFrame, weights.fillna(0.0))
