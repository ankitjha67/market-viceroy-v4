"""Drawdown-based risk metrics."""

from __future__ import annotations

from typing import TypeAlias

import numpy as np
import pandas as pd

ReturnLike: TypeAlias = pd.Series | np.ndarray


def _to_equity(returns_or_equity: ReturnLike, *, is_returns: bool = True) -> np.ndarray:
    """Coerce input to an equity curve.

    If ``is_returns`` is ``True`` (default), compound the periodic returns.
    Otherwise interpret the input as an equity curve directly.
    """
    arr = np.asarray(returns_or_equity, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"expected 1-D input, got shape {arr.shape}")
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return arr
    if is_returns:
        return np.cumprod(1.0 + arr)
    return arr


def max_drawdown(returns: ReturnLike) -> float:
    """Maximum drawdown of the compounded return series.

    Returned as a **negative** float (``-0.18`` means a 18% drawdown).
    Returns ``0.0`` for an empty or monotonically non-decreasing series.
    """
    equity = _to_equity(returns, is_returns=True)
    if equity.size == 0:
        return 0.0
    running_peak = np.maximum.accumulate(equity)
    drawdowns = (equity - running_peak) / running_peak
    return float(drawdowns.min())


def ulcer_index(returns: ReturnLike) -> float:
    """Ulcer Index — RMS of drawdowns expressed as a percentage.

    Peter Martin's metric. Lower is better. Penalises deep drawdowns
    more than frequent shallow ones.
    """
    equity = _to_equity(returns, is_returns=True)
    if equity.size == 0:
        return 0.0
    running_peak = np.maximum.accumulate(equity)
    drawdowns_pct = (equity - running_peak) / running_peak * 100.0
    return float(np.sqrt(np.mean(drawdowns_pct**2)))


def recovery_time(returns: ReturnLike) -> int:
    """Longest gap in bars between a peak and its full recovery.

    Returns ``0`` if the equity curve never drew down, or the length of
    the remaining window if the series ended before recovering.
    """
    equity = _to_equity(returns, is_returns=True)
    if equity.size == 0:
        return 0
    running_peak = np.maximum.accumulate(equity)
    underwater = equity < running_peak

    longest = 0
    current = 0
    for u in underwater:
        if u:
            current += 1
            if current > longest:
                longest = current
        else:
            current = 0
    # If the series ended underwater, the final run is the recovery time
    # we would still owe — count it.
    if current > longest:
        longest = current
    return int(longest)
