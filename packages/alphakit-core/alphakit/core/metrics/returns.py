"""Return-based performance metrics.

All functions accept ``pd.Series`` or ``np.ndarray`` of **periodic returns**
(fractional, not log) and return ``float``. Zero-variance inputs return
``0.0`` (not ``NaN``) to keep CI benchmark JSON serialisation clean.
"""

from __future__ import annotations

from typing import TypeAlias

import numpy as np
import pandas as pd
from alphakit.core.metrics.drawdown import max_drawdown

ReturnLike: TypeAlias = pd.Series | np.ndarray
"""Accepted input for every metric in this module."""


def _to_array(x: ReturnLike) -> np.ndarray:
    """Coerce to a contiguous 1-D ``float64`` array, dropping NaNs."""
    arr = np.asarray(x, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"expected 1-D returns, got shape {arr.shape}")
    return arr[~np.isnan(arr)]


def sharpe_ratio(
    returns: ReturnLike,
    *,
    risk_free_rate: float = 0.0,
    annualization: int = 252,
) -> float:
    """Annualised Sharpe ratio.

    ``(mean(returns) - rf_per_period) / std(returns) * sqrt(annualization)``

    Parameters
    ----------
    returns
        Periodic fractional returns.
    risk_free_rate
        Annualised risk-free rate, applied to each period as
        ``rf_per_period = risk_free_rate / annualization``.
    annualization
        Periods per year. 252 for daily, 52 for weekly, 12 for monthly.
    """
    arr = _to_array(returns)
    if arr.size < 2:
        return 0.0
    rf_per_period = risk_free_rate / annualization
    excess = arr - rf_per_period
    std = float(np.std(excess, ddof=1))
    if std == 0.0:
        return 0.0
    return float(np.mean(excess) / std * np.sqrt(annualization))


def sortino_ratio(
    returns: ReturnLike,
    *,
    risk_free_rate: float = 0.0,
    annualization: int = 252,
) -> float:
    """Annualised Sortino ratio (uses downside deviation).

    Only returns below zero (after excess) contribute to the denominator,
    so Sortino rewards upside volatility.
    """
    arr = _to_array(returns)
    if arr.size < 2:
        return 0.0
    rf_per_period = risk_free_rate / annualization
    excess = arr - rf_per_period
    downside = excess[excess < 0]
    if downside.size == 0:
        return 0.0
    # Downside deviation uses mean-square of negative excess, divided by N
    # (not N-1) — standard Sortino definition (Sortino & van der Meer 1991).
    downside_std = float(np.sqrt(np.mean(downside**2)))
    if downside_std == 0.0:
        return 0.0
    return float(np.mean(excess) / downside_std * np.sqrt(annualization))


def calmar_ratio(
    returns: ReturnLike,
    *,
    annualization: int = 252,
) -> float:
    """Calmar ratio: annualised return divided by absolute max drawdown.

    Computed from the compounded equity curve; this means Calmar depends
    on the order of returns, unlike Sharpe.
    """
    arr = _to_array(returns)
    if arr.size < 2:
        return 0.0
    equity = np.cumprod(1.0 + arr)
    years = arr.size / annualization
    if years <= 0:
        return 0.0
    ending_value = float(equity[-1])
    if ending_value <= 0:
        return 0.0
    annualised_return = ending_value ** (1.0 / years) - 1.0
    mdd = abs(max_drawdown(arr))
    if mdd == 0.0:
        return 0.0
    return float(annualised_return / mdd)


def information_ratio(
    returns: ReturnLike,
    benchmark_returns: ReturnLike,
    *,
    annualization: int = 252,
) -> float:
    """Annualised information ratio vs. a benchmark return series.

    ``mean(returns - benchmark) / std(returns - benchmark) * sqrt(annualization)``

    Returns ``0.0`` if the two series do not overlap or tracking error is
    zero.
    """
    arr = _to_array(returns)
    bench = _to_array(benchmark_returns)
    n = min(arr.size, bench.size)
    if n < 2:
        return 0.0
    active = arr[-n:] - bench[-n:]
    te = float(np.std(active, ddof=1))
    if te == 0.0:
        return 0.0
    return float(np.mean(active) / te * np.sqrt(annualization))
