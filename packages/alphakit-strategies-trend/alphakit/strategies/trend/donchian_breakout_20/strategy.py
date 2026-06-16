"""Donchian breakout, 20-day (Donchian 1960).

Paper
-----
Donchian, R. D. (1960). *High Finance in Copper*.
Financial Analysts Journal, 16(6), 133–142.
https://doi.org/10.2469/faj.v16.n6.133

Rules
-----
For each asset independently, at every bar:

* If the bar's close breaks above the trailing N-day high (excluding
  today), enter a long position.
* If the bar's close breaks below the trailing N-day low, exit any
  long and enter a short.
* Otherwise, hold the previous state.

The "previous state" is implemented here by running a state machine
across the price history and then mapping each state (long=+1,
short=-1, flat=0) to a weight. Per-asset weight is
``state / n_symbols`` — same multi-asset convention as the SMA
crosses — so the gross book is at most ±1 when every asset is
aligned.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


def _donchian_state(prices: pd.Series, window: int) -> pd.Series:
    """Compute the long/short/flat state for a single price series."""
    # Rolling high/low over the *prior* ``window`` bars, excluding today.
    rolling_high = prices.shift(1).rolling(window, min_periods=window).max()
    rolling_low = prices.shift(1).rolling(window, min_periods=window).min()

    state = np.zeros(len(prices), dtype=np.float64)
    high = rolling_high.to_numpy()
    low = rolling_low.to_numpy()
    close = prices.to_numpy()

    current = 0.0
    for i in range(len(prices)):
        if np.isnan(high[i]) or np.isnan(low[i]):
            state[i] = 0.0
            continue
        if close[i] > high[i]:
            current = 1.0
        elif close[i] < low[i]:
            current = -1.0
        state[i] = current

    return pd.Series(state, index=prices.index, name=prices.name)


class DonchianBreakout20:
    """20-day Donchian breakout (Donchian 1960)."""

    name: str = "donchian_breakout_20"
    family: str = "trend"
    asset_classes: tuple[str, ...] = ("equity", "future", "fx", "commodity", "crypto")
    paper_doi: str = "10.2469/faj.v16.n6.133"
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        window: int = 20,
        long_only: bool = False,
    ) -> None:
        if window <= 1:
            raise ValueError(f"window must be >= 2, got {window}")
        self.window = window
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

        states = {col: _donchian_state(prices[col], self.window) for col in prices.columns}
        signal = pd.DataFrame(states, index=prices.index)

        if self.long_only:
            signal = signal.clip(lower=0.0)

        weights = signal / len(prices.columns)
        return cast(pd.DataFrame, weights.fillna(0.0))
