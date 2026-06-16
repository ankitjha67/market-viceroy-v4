"""Full Turtle trading system (Dennis 1983 / Faith 2003).

Reference
---------
Faith, C. M. (2003). *Way of the Turtle: The Secret Methods that
Turned Ordinary People into Legendary Traders*. McGraw-Hill.
ISBN 978-0071486644.

What it is
----------
The Richard Dennis "Turtles" program (1983–1988) ran **two
independent Donchian breakout systems in parallel**:

* **System 1** — 20-day breakout entry, 10-day exit. Aggressive.
* **System 2** — 55-day breakout entry, 20-day exit. Slower.

An asset can be in both systems simultaneously. Position size is
scaled by ATR (``N``) so that a one-unit move is worth 1% of the
account. Pyramiding is allowed up to 4 units per asset.

This implementation (Phase 1)
-----------------------------
We run both systems as independent state machines (see the
``donchian_breakout_20`` and ``donchian_breakout_55`` strategies
for the primitives) and average their states to produce a combined
signal in ``{-1, -0.5, 0, 0.5, +1}``. Per-asset weight is
``combined_state / n_symbols`` — same multi-asset convention as the
rest of the trend family.

Deviations from the full Dennis program
---------------------------------------
* **No ATR-based unit sizing.** The paper uses ``unit = 1% / (N × $/point)``
  with N = 20-day ATR. Replacing the flat per-asset weight with
  ATR-scaled sizing is a Phase 4 add-on (``turtle_full_atr``).
* **No System 1 skip rule.** The real Turtles skip the next System 1
  trade after a winner; we take every signal.
* **No pyramiding.** Positions are binary (one unit) rather than
  building up to the four-unit cap.

These simplifications are all documented. The economic sign of the
signal — "be long this asset when it has broken out either over 20
or 55 days" — is preserved.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


def _breakout_state(prices: pd.Series, entry_window: int, exit_window: int) -> pd.Series:
    """Breakout state machine identical to donchian_breakout_55's helper."""
    rolling_high = prices.shift(1).rolling(entry_window, min_periods=entry_window).max()
    rolling_low = prices.shift(1).rolling(entry_window, min_periods=entry_window).min()
    rolling_low_exit = prices.shift(1).rolling(exit_window, min_periods=exit_window).min()
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
            if close[i] < rxl[i]:
                current = 0.0
            if close[i] < rl[i]:
                current = -1.0
        elif current == -1.0:
            if close[i] > rxh[i]:
                current = 0.0
            if close[i] > rh[i]:
                current = 1.0
        else:
            if close[i] > rh[i]:
                current = 1.0
            elif close[i] < rl[i]:
                current = -1.0
        state[i] = current

    return pd.Series(state, index=prices.index, name=prices.name)


class TurtleFull:
    """Full Turtle system — System 1 + System 2 combined (Faith 2003)."""

    name: str = "turtle_full"
    family: str = "trend"
    asset_classes: tuple[str, ...] = ("future", "commodity", "fx", "crypto")
    paper_doi: str = "978-0071486644"  # ISBN of Faith (2003)
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        system_1_entry: int = 20,
        system_1_exit: int = 10,
        system_2_entry: int = 55,
        system_2_exit: int = 20,
        long_only: bool = False,
    ) -> None:
        for name, value in [
            ("system_1_entry", system_1_entry),
            ("system_1_exit", system_1_exit),
            ("system_2_entry", system_2_entry),
            ("system_2_exit", system_2_exit),
        ]:
            if value <= 1:
                raise ValueError(f"{name} must be >= 2, got {value}")
        if system_1_exit >= system_1_entry:
            raise ValueError(
                f"system_1_exit ({system_1_exit}) must be < system_1_entry ({system_1_entry})"
            )
        if system_2_exit >= system_2_entry:
            raise ValueError(
                f"system_2_exit ({system_2_exit}) must be < system_2_entry ({system_2_entry})"
            )

        self.system_1_entry = system_1_entry
        self.system_1_exit = system_1_exit
        self.system_2_entry = system_2_entry
        self.system_2_exit = system_2_exit
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

        sys1 = pd.DataFrame(
            {
                col: _breakout_state(prices[col], self.system_1_entry, self.system_1_exit)
                for col in prices.columns
            },
            index=prices.index,
        )
        sys2 = pd.DataFrame(
            {
                col: _breakout_state(prices[col], self.system_2_entry, self.system_2_exit)
                for col in prices.columns
            },
            index=prices.index,
        )

        combined = (sys1 + sys2) / 2.0

        if self.long_only:
            combined = combined.clip(lower=0.0)

        weights = combined / len(prices.columns)
        return cast(pd.DataFrame, weights.fillna(0.0))
