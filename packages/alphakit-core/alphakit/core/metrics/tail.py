"""Tail-risk metrics: VaR, CVaR (a.k.a. Expected Shortfall), tail ratio.

Conventions
-----------
* ``confidence`` is the coverage of the *good* tail — e.g. ``0.95`` means
  "95% of the time the loss is no worse than this VaR". This matches
  the standard in Jorion (2007) and most practitioner texts.
* VaR and CVaR are reported as **negative** floats (losses). A 1-day
  99% VaR of ``-0.032`` means "losing more than 3.2% on any given day
  should happen only 1% of the time".
"""

from __future__ import annotations

from statistics import NormalDist
from typing import TypeAlias

import numpy as np
import pandas as pd

ReturnLike: TypeAlias = pd.Series | np.ndarray


def _clean(returns: ReturnLike) -> np.ndarray:
    arr = np.asarray(returns, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"expected 1-D returns, got shape {arr.shape}")
    return arr[~np.isnan(arr)]


def _check_confidence(confidence: float) -> None:
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")


def var_parametric(returns: ReturnLike, *, confidence: float = 0.95) -> float:
    """Parametric (Gaussian) Value at Risk.

    ``VaR = mean + z_alpha * std`` where ``z_alpha`` is the Gaussian
    quantile at ``1 - confidence``. Assumes returns are approximately
    normal — a strong assumption that fails for heavy-tailed series.
    """
    _check_confidence(confidence)
    arr = _clean(returns)
    if arr.size < 2:
        return 0.0
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1))
    if std == 0.0:
        return 0.0
    # Inverse normal CDF at 1 - confidence (stdlib, no scipy needed).
    alpha = 1.0 - confidence
    z = NormalDist().inv_cdf(alpha)
    return float(mean + z * std)


def var_historical(returns: ReturnLike, *, confidence: float = 0.95) -> float:
    """Historical (empirical) Value at Risk.

    No distributional assumption: simply the ``(1 - confidence)`` empirical
    quantile of the returns. More robust than parametric VaR for
    heavy-tailed series, but noisier for short samples.
    """
    _check_confidence(confidence)
    arr = _clean(returns)
    if arr.size == 0:
        return 0.0
    quantile = 1.0 - confidence
    # numpy.quantile uses linear interpolation, matching the ``quantile``
    # function in pandas.
    return float(np.quantile(arr, quantile))


def cvar(returns: ReturnLike, *, confidence: float = 0.95) -> float:
    """Conditional VaR (Expected Shortfall) at a given confidence level.

    Mean of returns in the tail beyond the historical VaR. Coherent risk
    measure (Artzner et al. 1999). Always ``<= VaR``.
    """
    _check_confidence(confidence)
    arr = _clean(returns)
    if arr.size == 0:
        return 0.0
    threshold = var_historical(arr, confidence=confidence)
    tail = arr[arr <= threshold]
    if tail.size == 0:
        return float(threshold)
    return float(np.mean(tail))


def tail_ratio(returns: ReturnLike, *, tail_percentile: float = 0.05) -> float:
    """Ratio of right tail to left tail at matching percentiles.

    ``abs(quantile(1 - p)) / abs(quantile(p))``. Values ``> 1`` mean
    upside tail dominates; values ``< 1`` mean downside tail dominates.

    Returns ``0.0`` when the left tail percentile is exactly zero (which
    would otherwise divide by zero).
    """
    if not 0.0 < tail_percentile < 0.5:
        raise ValueError(f"tail_percentile must be in (0, 0.5), got {tail_percentile}")
    arr = _clean(returns)
    if arr.size < 2:
        return 0.0
    right = abs(float(np.quantile(arr, 1.0 - tail_percentile)))
    left = abs(float(np.quantile(arr, tail_percentile)))
    if left == 0.0:
        return 0.0
    return right / left
