"""Monte-Carlo bootstrap of the Sharpe ratio (robustness, PRD FR-V2).

Resamples the out-of-sample returns to estimate a confidence interval and a
p-value for the Sharpe. Supports an i.i.d. bootstrap and a moving-block
bootstrap (preserves short-range autocorrelation). Deterministic: the caller
injects a ``numpy.random.Generator`` (seeded), so results are reproducible.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Bootstrap distribution summary for a Sharpe ratio."""

    sharpe: float  # point estimate (per-period)
    ci_low: float
    ci_high: float
    p_value: float  # fraction of resamples with Sharpe <= 0
    n_resamples: int


def _sharpe(returns: np.ndarray) -> float:
    std = float(returns.std(ddof=1))
    if std == 0.0:
        return 0.0
    return float(returns.mean() / std)


def _resample_indices(n: int, block_size: int, rng: np.random.Generator) -> np.ndarray:
    if block_size <= 1:
        return rng.integers(0, n, size=n)
    n_blocks = math.ceil(n / block_size)
    starts = rng.integers(0, n - block_size + 1, size=n_blocks)
    blocks = [np.arange(start, start + block_size) for start in starts]
    return np.concatenate(blocks)[:n]


def bootstrap_sharpe(
    returns: np.ndarray,
    *,
    rng: np.random.Generator,
    n_resamples: int = 1000,
    block_size: int = 1,
    confidence: float = 0.95,
) -> BootstrapResult:
    """Bootstrap the per-period Sharpe of ``returns``.

    Args:
        returns: 1-D array of per-period returns.
        rng: Seeded NumPy generator (determinism).
        n_resamples: Number of bootstrap resamples.
        block_size: 1 = i.i.d.; >1 = moving-block bootstrap.
        confidence: Two-sided CI level (e.g. 0.95 → [2.5%, 97.5%]).
    """
    values = np.asarray(returns, dtype=float)
    n = values.size
    if n < 2:
        raise ValueError("need at least 2 returns to bootstrap")
    if not 1 <= block_size <= n:
        raise ValueError("block_size must be in [1, len(returns)]")
    if n_resamples < 1:
        raise ValueError("n_resamples must be >= 1")

    sims = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        sims[i] = _sharpe(values[_resample_indices(n, block_size, rng)])

    alpha = (1.0 - confidence) / 2.0
    return BootstrapResult(
        sharpe=_sharpe(values),
        ci_low=float(np.quantile(sims, alpha)),
        ci_high=float(np.quantile(sims, 1.0 - alpha)),
        p_value=float(np.mean(sims <= 0.0)),
        n_resamples=n_resamples,
    )
