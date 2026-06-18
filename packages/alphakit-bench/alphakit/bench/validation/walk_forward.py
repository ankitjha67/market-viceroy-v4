"""Walk-forward evaluation (PRD FR-V2) — rolling out-of-sample windows.

For each test window the strategy is backtested on data **only up to that
window's end** (no look-ahead), and just the window's out-of-sample returns are
kept. The stitched OOS returns and the per-window consistency (share of
positive windows, worst window) are what the gate judges — a strategy that only
works in one window is not credible. Reuses the vectorbt bridge; no engine
re-implementation. The catalog strategies have fixed configs, so this is rolling
OOS evaluation rather than literal re-optimization.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from alphakit.bridges import vectorbt_bridge
from alphakit.core.metrics.returns import sharpe_ratio
from alphakit.core.protocols import StrategyProtocol


@dataclass(frozen=True, slots=True)
class WindowResult:
    """One out-of-sample window's outcome."""

    start: int
    end: int
    sharpe: float
    n_obs: int


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    """Aggregate walk-forward outcome across all windows."""

    windows: list[WindowResult]
    oos_returns: np.ndarray
    aggregate_sharpe: float
    positive_window_fraction: float
    worst_window_sharpe: float


def walk_forward(
    strategy: StrategyProtocol,
    prices: pd.DataFrame,
    *,
    test_size: int,
    step: int,
    min_train: int = 252,
    commission_bps: float = 5.0,
    slippage_bps: float = 0.0,
    annualization: int = 252,
) -> WalkForwardResult:
    """Roll a fixed-size OOS test window forward, re-running per window.

    Args:
        strategy: The strategy to evaluate.
        prices: Price panel (DatetimeIndex × symbols).
        test_size: Length (bars) of each OOS test window.
        step: Bars to advance the window each iteration.
        min_train: Minimum history before the first test window.
        commission_bps / slippage_bps: Cost-aware backtest inputs.
        annualization: Periods per year for Sharpe.

    Raises:
        ValueError: On non-positive sizes or too little data for one window.
    """
    if test_size <= 0 or step <= 0:
        raise ValueError("test_size and step must be positive")
    n = len(prices)
    if n < min_train + test_size:
        raise ValueError("not enough data for a single walk-forward window")

    windows: list[WindowResult] = []
    oos_slices: list[np.ndarray] = []
    end = min_train + test_size
    while end <= n:
        start = end - test_size
        result = vectorbt_bridge.run(
            strategy,
            prices.iloc[:end],
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
        )
        window_returns = result.returns.iloc[start:end].to_numpy()
        sharpe = sharpe_ratio(window_returns, annualization=annualization)
        windows.append(WindowResult(start=start, end=end, sharpe=sharpe, n_obs=len(window_returns)))
        oos_slices.append(window_returns)
        end += step

    oos = np.concatenate(oos_slices)
    positive = sum(1 for w in windows if w.sharpe > 0)
    return WalkForwardResult(
        windows=windows,
        oos_returns=oos,
        aggregate_sharpe=sharpe_ratio(oos, annualization=annualization),
        positive_window_fraction=positive / len(windows),
        worst_window_sharpe=min(w.sharpe for w in windows),
    )
