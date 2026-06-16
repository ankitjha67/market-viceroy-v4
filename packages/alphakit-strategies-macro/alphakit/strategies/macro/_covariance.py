"""Shared covariance-estimation and portfolio-construction primitives.

Three Session 2G strategies — ``risk_parity_erc_3asset``,
``min_variance_gtaa``, and ``max_diversification`` — all require joint
covariance estimation followed by numerical weight optimisation. This
module centralises that pipeline so the three strategies share a single
estimator and three solvers built on top of it.

Why a shared helper
-------------------

1. **Code duplication.** A per-strategy reimplementation of rolling
   covariance + Ledoit-Wolf shrinkage + a long-only constrained
   optimiser would duplicate ~200 lines across three strategies.
2. **Cluster-prediction integrity.** Phase 2 cluster analysis depends
   on strategies in the same family sharing data-pipeline assumptions
   so that differences in cluster correlations reflect methodological
   differences (ERC vs minimum variance vs maximum diversification),
   not arbitrary divergences in the covariance estimator. A shared
   helper enforces that.
3. **Numerical-guard consistency.** The singular-covariance fallback
   (N ≥ T degenerate case), the positive-definite check, and the
   long-only feasibility check are non-trivial; implementing them
   once in a tested helper is safer than three times.

The helper is stateless — every function takes its inputs and returns
its outputs without mutating shared state. No globals, no caches, no
implicit configuration.

Shrinkage estimator
-------------------

The default is Ledoit & Wolf (2004) shrinkage toward a constant-
correlation target. The shrinkage intensity ``δ`` is computed
analytically from the sample (no cross-validation required) and is
guaranteed to lie in ``[0, 1]``. Reference:

    Ledoit, O. & Wolf, M. (2004). *Honey, I shrunk the sample
    covariance matrix.* Journal of Portfolio Management 30(4),
    110-119. DOI: 10.3905/jpm.2004.110

Implementation follows the authors' published MATLAB reference
(`shrinkage_corr.m`) translated to NumPy.

ERC solver
----------

Equal-risk-contribution weights are computed via the convex
reformulation of Spinu (2013), which Maillard, Roncalli & Teiletche
(2010) prove is equivalent to the ERC problem:

    min_w  (1/2) wᵀ Σ w − (1/N) Σᵢ log(wᵢ)
    s.t.   wᵢ > 0

At the optimum each asset contributes equal marginal risk to portfolio
volatility. The objective is strictly convex, so any local optimiser
converges to the global solution. We use SciPy's L-BFGS-B with simple
lower-bound box constraints (``wᵢ ≥ 1e-10``).

Minimum-variance and maximum-diversification solvers
----------------------------------------------------

Both are constrained nonlinear programs:

    min_w  wᵀ Σ w                                (minimum variance)
    max_w  (wᵀ σ) / sqrt(wᵀ Σ w)                  (maximum diversification)
    s.t.   sum(w) = 1, 0 ≤ wᵢ ≤ w_max

Solved via SciPy SLSQP. The diversification-ratio objective follows
Choueifaty & Coignard (2008).

Numerical guards
----------------

* ``N == 1`` (single asset) → all solvers return ``[1.0]``.
* ``T_eff < N`` (more assets than effective observations) → sample
  covariance is rank-deficient. ``rolling_covariance`` falls back
  from ``ledoit_wolf`` / ``constant`` shrinkage to ``np.cov(clean.T,
  ddof=1)`` for that date (still emits a row in the output, just
  without shrinkage applied). The resulting matrix is positive
  *semi*-definite (rank ≤ T_eff), not positive-definite. Downstream
  solvers may struggle on near-singular inputs: ``solve_erc_weights``
  raises ``ValueError`` on zero-diagonal assets; SLSQP-based
  ``solve_min_variance_weights`` and
  ``solve_max_diversification_weights`` may converge to interior
  feasible points but do not pseudo-inverse the covariance. Callers
  that need a robust N≥T regime should switch to ``shrinkage=
  "constant"`` (always emits a positive-definite matrix because the
  target is positive-definite and α=0.5 is fixed) or supply a
  longer ``window``.
* Any asset with zero or negative sample variance triggers a
  ``ValueError`` (cannot allocate weight to a non-stochastic asset).
* ERC iteration with degenerate marginal risks (``Σw ≤ 0``, possible
  with negative-correlation pathologies) falls back to inverse-volatility
  weights rather than failing silently.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ShrinkageMethod = Literal["none", "ledoit_wolf", "constant"]


def _ledoit_wolf_shrinkage(returns_demeaned: np.ndarray) -> tuple[np.ndarray, float]:
    """Ledoit-Wolf 2004 shrinkage toward a constant-correlation target.

    Parameters
    ----------
    returns_demeaned
        Demeaned (T, N) returns matrix. The caller is responsible for
        subtracting the column means.

    Returns
    -------
    (cov_shrunk, alpha)
        The shrunken (N, N) covariance estimate and the shrinkage
        intensity ``α ∈ [0, 1]``. ``α = 0`` means no shrinkage (use
        sample); ``α = 1`` means full shrinkage to the target.
    """
    x = returns_demeaned
    t_obs, n_assets = x.shape
    if t_obs < 2 or n_assets < 2:
        raise ValueError(
            f"_ledoit_wolf_shrinkage requires T>=2 and N>=2; got T={t_obs}, N={n_assets}"
        )

    sample = (x.T @ x) / t_obs

    var = np.diag(sample)
    if (var <= 0).any():
        raise ValueError(
            f"Sample variance must be positive for all assets; got diag(sample) = {var.tolist()}"
        )
    sqrtvar = np.sqrt(var)
    sqrtvar_outer = np.outer(sqrtvar, sqrtvar)

    r_bar = (np.sum(sample / sqrtvar_outer) - n_assets) / (n_assets * (n_assets - 1))
    target = r_bar * sqrtvar_outer
    np.fill_diagonal(target, var)

    y = x**2
    phi_mat = (y.T @ y) / t_obs - sample**2
    phi = float(phi_mat.sum())

    term1 = (x**3).T @ x / t_obs
    help_diag = var
    term2 = help_diag[:, None] * sample
    term3 = sample * var[None, :]
    term4 = var[:, None] * sample
    theta_mat = term1 - term2 - term3 + term4
    np.fill_diagonal(theta_mat, 0.0)
    rho = float(np.diag(phi_mat).sum()) + r_bar * float(
        np.sum(((1.0 / sqrtvar)[:, None] * sqrtvar[None, :]) * theta_mat)
    )

    gamma = float(np.sum((sample - target) ** 2))

    if gamma <= 0:
        alpha = 0.0
    else:
        kappa = (phi - rho) / gamma
        alpha = float(max(0.0, min(1.0, kappa / t_obs)))

    cov_shrunk = alpha * target + (1.0 - alpha) * sample
    return cov_shrunk, alpha


def _constant_target_shrinkage(returns_demeaned: np.ndarray, alpha: float = 0.5) -> np.ndarray:
    """Fixed-intensity shrinkage to a constant-correlation target.

    Same target as Ledoit-Wolf but with a user-specified intensity
    rather than the analytic optimum. Used when the strategy author
    wants a deterministic shrinkage independent of sample size.
    """
    x = returns_demeaned
    t_obs = x.shape[0]
    sample = (x.T @ x) / t_obs
    var = np.diag(sample)
    if (var <= 0).any():
        raise ValueError("Sample variance must be positive for all assets.")
    sqrtvar = np.sqrt(var)
    n_assets = x.shape[1]
    r_bar = (np.sum(sample / np.outer(sqrtvar, sqrtvar)) - n_assets) / (n_assets * (n_assets - 1))
    target = r_bar * np.outer(sqrtvar, sqrtvar)
    np.fill_diagonal(target, var)
    return np.asarray(alpha * target + (1.0 - alpha) * sample, dtype=float)


def rolling_covariance(
    returns: pd.DataFrame,
    window: int = 252,
    shrinkage: ShrinkageMethod = "ledoit_wolf",
) -> pd.DataFrame:
    """Rolling covariance with optional shrinkage.

    Parameters
    ----------
    returns
        Wide DataFrame indexed by date, columns are asset names. Each
        cell is a return (log or arithmetic — the helper does not care,
        but downstream solvers assume consistent units).
    window
        Trailing window in observations. Default 252 (one trading year
        of daily returns).
    shrinkage
        ``"none"``        → raw sample covariance (``np.cov`` with
                            ``ddof=1``).
        ``"ledoit_wolf"`` → Ledoit-Wolf 2004 shrinkage to a constant-
                            correlation target with analytic optimal
                            intensity (default).
        ``"constant"``    → fixed-intensity (α = 0.5) shrinkage to the
                            same target. Used when the strategy author
                            wants a deterministic shrinkage independent
                            of sample size.

    Returns
    -------
    DataFrame indexed by ``MultiIndex(date, asset_i)``, columns are
    ``asset_j``. ``df.loc[date]`` returns the (N, N) covariance matrix
    at that date as a regular DataFrame. Dates before ``window``
    observations are available are omitted from the output; dates where
    the window contains fewer than ``window // 2`` non-NaN rows
    are also omitted.

    Raises
    ------
    ValueError
        If ``window < 2`` or ``returns`` has fewer than 2 columns.
    """
    if window < 2:
        raise ValueError(f"window must be >= 2, got {window}")
    if shrinkage not in ("none", "ledoit_wolf", "constant"):
        raise ValueError(
            f"shrinkage must be 'none', 'ledoit_wolf', or 'constant'; got {shrinkage!r}"
        )
    n_assets = returns.shape[1]
    if n_assets < 2:
        raise ValueError(f"rolling_covariance requires >= 2 assets; got {n_assets}")

    asset_names = list(returns.columns)
    matrices: dict[pd.Timestamp, pd.DataFrame] = {}

    for t_idx in range(window - 1, len(returns)):
        window_data = returns.iloc[t_idx - window + 1 : t_idx + 1]
        window_arr = window_data.to_numpy(dtype=float)
        valid_rows = ~np.isnan(window_arr).any(axis=1)
        if int(valid_rows.sum()) < window // 2:
            continue
        clean = window_arr[valid_rows]
        t_eff = clean.shape[0]
        demeaned = clean - clean.mean(axis=0)

        if t_eff < n_assets or shrinkage == "none":
            cov_mat = np.cov(clean.T, ddof=1)
        elif shrinkage == "ledoit_wolf":
            cov_mat, _ = _ledoit_wolf_shrinkage(demeaned)
        else:  # "constant"
            cov_mat = _constant_target_shrinkage(demeaned)

        matrices[returns.index[t_idx]] = pd.DataFrame(
            cov_mat, index=asset_names, columns=asset_names
        )

    if not matrices:
        empty_index = pd.MultiIndex.from_arrays([[], []], names=["date", "asset"])
        return pd.DataFrame(index=empty_index, columns=asset_names, dtype=float)

    return pd.concat(matrices, names=["date", "asset"])


def solve_erc_weights(cov: np.ndarray, max_iters: int = 1000, tol: float = 1e-8) -> np.ndarray:
    """Equal-risk-contribution portfolio weights.

    Solves the Spinu (2013) convex reformulation of the ERC problem
    (Maillard, Roncalli & Teiletche 2010):

        min_w  (1/2) wᵀ Σ w − (1/N) Σᵢ log(wᵢ)
        s.t.   wᵢ > 0

    At the optimum each asset's risk contribution
    ``w_i · (Σw)_i / sqrt(wᵀΣw)`` is equal across ``i``. Weights are
    L-1-normalised before return so ``sum(w) == 1``.

    Parameters
    ----------
    cov
        (N, N) covariance matrix. Must be positive-definite with
        strictly positive diagonal.
    max_iters
        Maximum L-BFGS-B iterations.
    tol
        Convergence tolerance on the objective.

    Returns
    -------
    Length-N weight array, all strictly positive, summing to 1.0.

    Raises
    ------
    ValueError
        If ``cov`` is not square, has non-positive diagonal, or the
        optimiser fails.
    """
    cov = np.asarray(cov, dtype=float)
    if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
        raise ValueError(f"cov must be square 2D; got shape {cov.shape}")
    n_assets = cov.shape[0]
    if n_assets == 1:
        return np.array([1.0])

    vols = np.sqrt(np.diag(cov))
    if (vols <= 0).any():
        raise ValueError(
            f"All assets must have positive variance; got diag(cov) = {np.diag(cov).tolist()}"
        )

    w0 = 1.0 / vols
    w0 = w0 / w0.sum()

    def objective(w: np.ndarray) -> float:
        return float(0.5 * w @ cov @ w - np.sum(np.log(w)) / n_assets)

    def gradient(w: np.ndarray) -> np.ndarray:
        return np.asarray(cov @ w - 1.0 / (n_assets * w), dtype=float)

    bounds = [(1e-12, None)] * n_assets
    result = minimize(
        objective,
        w0,
        jac=gradient,
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": max_iters, "ftol": tol},
    )
    if not result.success:
        raise ValueError(f"ERC optimiser failed: {result.message}; weights = {result.x.tolist()}")
    w = np.asarray(result.x, dtype=float)
    return np.asarray(w / w.sum(), dtype=float)


def solve_min_variance_weights(
    cov: np.ndarray, long_only: bool = True, max_weight: float = 1.0
) -> np.ndarray:
    """Minimum-variance portfolio weights.

    Solves

        min_w  wᵀ Σ w
        s.t.   sum(w) = 1
               −max_weight ≤ wᵢ ≤ max_weight   (long_only=False)
               0 ≤ wᵢ ≤ max_weight             (long_only=True)

    via SciPy SLSQP.

    Parameters
    ----------
    cov
        (N, N) positive-semidefinite covariance matrix.
    long_only
        If True (default), constrain ``wᵢ ≥ 0``.
    max_weight
        Per-asset upper bound on weight magnitude. Default 1.0
        (concentration up to the full portfolio in a single asset
        is allowed; tighter caps reduce concentration risk).

    Returns
    -------
    Length-N weight array summing to 1.0.

    Raises
    ------
    ValueError
        If ``cov`` is not square or the optimiser fails.
    """
    cov = np.asarray(cov, dtype=float)
    if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
        raise ValueError(f"cov must be square 2D; got shape {cov.shape}")
    n_assets = cov.shape[0]
    if n_assets == 1:
        return np.array([1.0])
    if max_weight <= 0:
        raise ValueError(f"max_weight must be > 0; got {max_weight}")

    def objective(w: np.ndarray) -> float:
        return float(w @ cov @ w)

    def gradient(w: np.ndarray) -> np.ndarray:
        return np.asarray(2.0 * cov @ w, dtype=float)

    constraints = [
        {
            "type": "eq",
            "fun": lambda w: float(w.sum() - 1.0),
            "jac": lambda w: np.ones(n_assets),
        }
    ]
    bounds = [(0.0, max_weight)] * n_assets if long_only else [(-max_weight, max_weight)] * n_assets

    w0 = np.ones(n_assets) / n_assets
    result = minimize(
        objective,
        w0,
        jac=gradient,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-10, "maxiter": 500},
    )
    if not result.success:
        raise ValueError(
            f"Min-variance optimiser failed: {result.message}; weights = {result.x.tolist()}"
        )
    w = np.asarray(result.x, dtype=float)
    total = w.sum()
    if total <= 0:
        raise ValueError(f"Min-variance optimiser produced non-positive total weight {total}")
    return np.asarray(w / total, dtype=float)


def diversification_ratio(weights: np.ndarray, cov: np.ndarray) -> float:
    """Choueifaty-Coignard (2008) diversification ratio.

    DR(w) = (wᵀ σ) / sqrt(wᵀ Σ w)

    where ``σ`` is the vector of individual asset volatilities
    (``sqrt(diag(Σ))``). DR ≥ 1 for any valid long-only portfolio;
    DR = 1 means the portfolio behaves as a single concentrated asset;
    higher DR means more diversification benefit from cross-asset
    correlations.

    Parameters
    ----------
    weights
        Length-N weight array. May be unnormalised; DR is scale-
        invariant in ``w``.
    cov
        (N, N) covariance matrix.

    Returns
    -------
    The diversification ratio as a float. Returns 0.0 if portfolio
    variance is non-positive (degenerate input).
    """
    weights = np.asarray(weights, dtype=float)
    cov = np.asarray(cov, dtype=float)
    vols = np.sqrt(np.diag(cov))
    weighted_avg_vol = float(weights @ vols)
    portfolio_var = float(weights @ cov @ weights)
    if portfolio_var <= 0:
        return 0.0
    return weighted_avg_vol / float(np.sqrt(portfolio_var))


def solve_max_diversification_weights(
    cov: np.ndarray, long_only: bool = True, max_weight: float = 1.0
) -> np.ndarray:
    """Maximum-diversification portfolio weights (Choueifaty-Coignard 2008).

    Maximises the diversification ratio

        DR(w) = (wᵀ σ) / sqrt(wᵀ Σ w)

    subject to ``sum(w) = 1`` and box constraints. Equivalent to
    minimising ``−DR`` via SLSQP.

    Parameters
    ----------
    cov
        (N, N) positive-semidefinite covariance matrix.
    long_only
        If True (default), constrain ``wᵢ ≥ 0``.
    max_weight
        Per-asset upper bound on weight magnitude. Default 1.0.

    Returns
    -------
    Length-N weight array summing to 1.0.

    Raises
    ------
    ValueError
        If ``cov`` is not square or the optimiser fails.
    """
    cov = np.asarray(cov, dtype=float)
    if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
        raise ValueError(f"cov must be square 2D; got shape {cov.shape}")
    n_assets = cov.shape[0]
    if n_assets == 1:
        return np.array([1.0])
    if max_weight <= 0:
        raise ValueError(f"max_weight must be > 0; got {max_weight}")

    vols = np.sqrt(np.diag(cov))
    if (vols <= 0).any():
        raise ValueError(
            f"All assets must have positive variance; got diag(cov) = {np.diag(cov).tolist()}"
        )

    def neg_diversification(w: np.ndarray) -> float:
        portfolio_var = float(w @ cov @ w)
        if portfolio_var <= 0:
            return 0.0
        return -float(w @ vols) / float(np.sqrt(portfolio_var))

    constraints = [
        {
            "type": "eq",
            "fun": lambda w: float(w.sum() - 1.0),
            "jac": lambda w: np.ones(n_assets),
        }
    ]
    bounds = [(0.0, max_weight)] * n_assets if long_only else [(-max_weight, max_weight)] * n_assets

    w0 = np.ones(n_assets) / n_assets
    result = minimize(
        neg_diversification,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-10, "maxiter": 500},
    )
    if not result.success:
        raise ValueError(
            f"Max-diversification optimiser failed: {result.message}; weights = {result.x.tolist()}"
        )
    w = np.asarray(result.x, dtype=float)
    total = w.sum()
    if total <= 0:
        raise ValueError(
            f"Max-diversification optimiser produced non-positive total weight {total}"
        )
    return np.asarray(w / total, dtype=float)


__all__ = [
    "ShrinkageMethod",
    "diversification_ratio",
    "rolling_covariance",
    "solve_erc_weights",
    "solve_max_diversification_weights",
    "solve_min_variance_weights",
]
