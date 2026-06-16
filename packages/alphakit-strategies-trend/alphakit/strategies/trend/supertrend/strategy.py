"""Supertrend ATR-based trailing-stop filter.

Reference (ATR primitive)
-------------------------
Wilder, J. W. (1978). *New Concepts in Technical Trading Systems*.
Trend Research. ISBN 0-89459-027-8.

Wilder invented the Average True Range (ATR) in 1978. The Supertrend
indicator itself is practitioner lore, first popularised in the
mid-2000s (Olivier Seban's work in French trading publications and,
later, TradingView's stock library). There is no formal academic
citation for Supertrend; we cite Wilder 1978 as the origin of the
ATR that the indicator is built on.

Algorithm
---------
For each asset independently:

1. Compute a rolling ATR proxy (mean absolute close-to-close change
   over ``atr_period`` bars — a close-only simplification of Wilder's
   full high/low/close-based ATR).
2. Build two bands around the close:

       upper = close + multiplier * atr
       lower = close - multiplier * atr

3. Run a state machine that flips long when close crosses above the
   prior upper band, and flips short when close crosses below the
   prior lower band. Between flips the state persists.

Per-asset weight is ``state / n_symbols`` — same multi-asset
convention as the rest of the trend family.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


def _supertrend_state(prices: pd.Series, atr_period: int, multiplier: float) -> pd.Series:
    """State machine for a single asset."""
    deltas = prices.diff().abs()
    atr = deltas.rolling(atr_period, min_periods=atr_period).mean()

    upper = (prices + multiplier * atr).to_numpy()
    lower = (prices - multiplier * atr).to_numpy()
    close = prices.to_numpy()

    state = np.zeros(len(prices), dtype=np.float64)
    current = 0.0
    for i in range(1, len(prices)):
        prev_upper = upper[i - 1]
        prev_lower = lower[i - 1]
        if np.isnan(prev_upper) or np.isnan(prev_lower):
            state[i] = 0.0
            continue
        if current == 1.0:
            if close[i] < prev_lower:
                current = -1.0
        elif current == -1.0:
            if close[i] > prev_upper:
                current = 1.0
        else:
            if close[i] > prev_upper:
                current = 1.0
            elif close[i] < prev_lower:
                current = -1.0
        state[i] = current

    return pd.Series(state, index=prices.index, name=prices.name)


class Supertrend:
    """Supertrend ATR trailing-stop filter."""

    name: str = "supertrend"
    family: str = "trend"
    asset_classes: tuple[str, ...] = ("equity", "future", "fx", "commodity", "crypto")
    paper_doi: str = "0-89459-027-8"  # Wilder (1978) ISBN
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        atr_period: int = 10,
        multiplier: float = 3.0,
        long_only: bool = False,
    ) -> None:
        if atr_period <= 1:
            raise ValueError(f"atr_period must be >= 2, got {atr_period}")
        if multiplier <= 0:
            raise ValueError(f"multiplier must be positive, got {multiplier}")
        self.atr_period = atr_period
        self.multiplier = multiplier
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
            col: _supertrend_state(prices[col], self.atr_period, self.multiplier)
            for col in prices.columns
        }
        signal = pd.DataFrame(states, index=prices.index)

        if self.long_only:
            signal = signal.clip(lower=0.0)

        weights = signal / len(prices.columns)
        return cast(pd.DataFrame, weights.fillna(0.0))
