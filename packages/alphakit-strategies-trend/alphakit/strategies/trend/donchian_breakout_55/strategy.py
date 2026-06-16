"""Donchian 55-day breakout — the slow arm of the Dennis Turtle system.

Papers
------
Donchian, R. D. (1960). *High Finance in Copper*. Financial Analysts
Journal, 16(6), 133–142. https://doi.org/10.2469/faj.v16.n6.133

Faith, C. M. (2003). *Way of the Turtle*. McGraw-Hill.
ISBN 978-0071486644.

Rules
-----
Same state machine as `donchian_breakout_20`, but the breakout is
relative to the trailing 55-day high and the exit to the trailing
20-day low. This configuration ("System 2" in the original Turtle
program) is slower but much less prone to whipsaws than the 20/10
variant.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


def _donchian_state(prices: pd.Series, entry_window: int, exit_window: int) -> pd.Series:
    """Long on break above entry-window high; exit on break below exit-window low.

    Short side is symmetric. Between breakouts the state persists.
    """
    rolling_high = prices.shift(1).rolling(entry_window, min_periods=entry_window).max()
    rolling_low_exit = prices.shift(1).rolling(exit_window, min_periods=exit_window).min()
    rolling_low = prices.shift(1).rolling(entry_window, min_periods=entry_window).min()
    rolling_high_exit = prices.shift(1).rolling(exit_window, min_periods=exit_window).max()

    state = np.zeros(len(prices), dtype=np.float64)
    rh = rolling_high.to_numpy()
    rl = rolling_low.to_numpy()
    rxl = rolling_low_exit.to_numpy()
    rxh = rolling_high_exit.to_numpy()
    close = prices.to_numpy()

    current = 0.0
    for i in range(len(prices)):
        if np.isnan(rh[i]) or np.isnan(rl[i]) or np.isnan(rxl[i]) or np.isnan(rxh[i]):
            state[i] = 0.0
            continue
        if current == 1.0:
            # Long: exit on break below exit-window low, then maybe flip short.
            if close[i] < rxl[i]:
                current = 0.0
            if close[i] < rl[i]:
                current = -1.0
        elif current == -1.0:
            if close[i] > rxh[i]:
                current = 0.0
            if close[i] > rh[i]:
                current = 1.0
        else:  # flat
            if close[i] > rh[i]:
                current = 1.0
            elif close[i] < rl[i]:
                current = -1.0
        state[i] = current

    return pd.Series(state, index=prices.index, name=prices.name)


class DonchianBreakout55:
    """55-day Donchian breakout with 20-day exit (Dennis Turtle System 2)."""

    name: str = "donchian_breakout_55"
    family: str = "trend"
    asset_classes: tuple[str, ...] = ("equity", "future", "fx", "commodity", "crypto")
    paper_doi: str = "10.2469/faj.v16.n6.133"
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        entry_window: int = 55,
        exit_window: int = 20,
        long_only: bool = False,
    ) -> None:
        if entry_window <= 1:
            raise ValueError(f"entry_window must be >= 2, got {entry_window}")
        if exit_window <= 1:
            raise ValueError(f"exit_window must be >= 2, got {exit_window}")
        if exit_window >= entry_window:
            raise ValueError(f"exit_window ({exit_window}) must be < entry_window ({entry_window})")
        self.entry_window = entry_window
        self.exit_window = exit_window
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

        states = {
            col: _donchian_state(prices[col], self.entry_window, self.exit_window)
            for col in prices.columns
        }
        signal = pd.DataFrame(states, index=prices.index)

        if self.long_only:
            signal = signal.clip(lower=0.0)

        weights = signal / len(prices.columns)
        return cast(pd.DataFrame, weights.fillna(0.0))
