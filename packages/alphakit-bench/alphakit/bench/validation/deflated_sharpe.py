"""Probabilistic + Deflated Sharpe Ratio (Bailey & López de Prado).

The multiple-testing correction at the heart of "validated, not proven": a high
Sharpe is only credible once deflated for the number of trials, the track
length, and the return distribution's skew/kurtosis. Pure — uses
``statistics.NormalDist`` for the normal CDF/quantile (no scipy).

All Sharpe inputs here are **per-period** (non-annualized): divide an annualized
Sharpe by ``sqrt(annualization)`` before passing it in.
"""

from __future__ import annotations

import math
from statistics import NormalDist

_NORMAL = NormalDist()
_EULER_MASCHERONI = 0.5772156649015329


def probabilistic_sharpe_ratio(
    sharpe: float,
    n_obs: int,
    *,
    benchmark_sharpe: float = 0.0,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Probability that the true (per-period) Sharpe exceeds ``benchmark_sharpe``.

    PSR = Φ( (SR − SR*)·√(n−1) / √(1 − γ3·SR + ((γ4−1)/4)·SR²) ), where γ3 is
    skew and γ4 is (non-excess) kurtosis (3 for a normal distribution).
    Returns a probability in [0, 1].
    """
    if n_obs < 2:
        raise ValueError("n_obs must be >= 2")
    variance_term = 1.0 - skew * sharpe + ((kurtosis - 1.0) / 4.0) * sharpe**2
    if variance_term <= 0.0:
        # Degenerate distribution shape; treat as no information.
        return 0.5
    z = (sharpe - benchmark_sharpe) * math.sqrt(n_obs - 1) / math.sqrt(variance_term)
    return _NORMAL.cdf(z)


def expected_max_sharpe(n_trials: int, trials_sharpe_std: float) -> float:
    """Expected maximum Sharpe from ``n_trials`` independent trials (per-period).

    E[max SR] ≈ σ·[ (1−γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e)) ], with γ the
    Euler–Mascheroni constant and σ the cross-trial Sharpe dispersion. This is
    the benchmark a single strategy must clear to be credible under selection.
    """
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1")
    if trials_sharpe_std < 0:
        raise ValueError("trials_sharpe_std must be non-negative")
    if n_trials == 1:
        return 0.0
    gamma = _EULER_MASCHERONI
    q1 = _NORMAL.inv_cdf(1.0 - 1.0 / n_trials)
    q2 = _NORMAL.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    return trials_sharpe_std * ((1.0 - gamma) * q1 + gamma * q2)


def deflated_sharpe_ratio(
    sharpe: float,
    n_obs: int,
    *,
    n_trials: int,
    trials_sharpe_std: float,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Deflated Sharpe: PSR benchmarked against the expected maximum Sharpe.

    DSR ≈ 1 means the Sharpe survives the multiple-testing deflation; DSR near
    0 means it is indistinguishable from the best of ``n_trials`` lucky draws.
    """
    benchmark = expected_max_sharpe(n_trials, trials_sharpe_std)
    return probabilistic_sharpe_ratio(
        sharpe,
        n_obs,
        benchmark_sharpe=benchmark,
        skew=skew,
        kurtosis=kurtosis,
    )
