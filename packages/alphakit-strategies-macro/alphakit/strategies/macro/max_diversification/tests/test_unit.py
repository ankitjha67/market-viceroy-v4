"""Unit tests for max_diversification signal generation.

Third consumer of the shared ``_covariance`` helper module —
tests verify the strategy correctly consumes
``rolling_covariance`` and ``solve_max_diversification_weights``
and produces MDP weights with the expected mathematical
properties (sum-to-1, non-negative, diversification-ratio
maximisation).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.macro._covariance import diversification_ratio
from alphakit.strategies.macro.max_diversification.strategy import MaxDiversification


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2018-01-01", periods=n_days, freq="B")


def _gbm_panel(
    symbols: list[str],
    years: float,
    drifts: tuple[float, ...],
    vols: tuple[float, ...],
    correlations: np.ndarray | None = None,
    seed: int = 7,
) -> pd.DataFrame:
    """Geometric-Brownian-motion panel with configurable per-asset
    drift, vol, and optional correlation matrix."""
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = _daily_index(years)
    n = len(symbols)
    if correlations is None:
        correlations = np.eye(n)
    cov = np.outer(np.asarray(vols), np.asarray(vols)) * correlations / np.sqrt(252)
    shocks = rng.multivariate_normal(np.asarray(drifts) / 252, cov, size=n_days)
    log_prices = np.cumsum(shocks, axis=0)
    return pd.DataFrame(100.0 * np.exp(log_prices), index=index, columns=symbols)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(MaxDiversification(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = MaxDiversification()
    assert s.name == "max_diversification"
    assert s.family == "macro"
    assert s.paper_doi == "10.2139/ssrn.1895459"  # CFR 2013
    assert s.rebalance_frequency == "monthly"
    assert s.asset_classes == ("equity", "bonds", "commodities")


def test_required_symbols_are_default_three() -> None:
    s = MaxDiversification()
    assert s.required_symbols == ("SPY", "TLT", "DBC")


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"stocks_symbol": ""}, "stocks_symbol"),
        ({"bonds_symbol": ""}, "bonds_symbol"),
        ({"commodities_symbol": ""}, "commodities_symbol"),
        ({"cov_window_days": 30}, "cov_window_days must be >= 60"),
        ({"shrinkage": "bogus"}, "shrinkage must be"),
        ({"max_weight": 0.0}, "max_weight must be in"),
        ({"max_weight": 1.5}, "max_weight must be in"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        MaxDiversification(**kwargs)  # type: ignore[arg-type]


def test_constructor_rejects_duplicate_symbols() -> None:
    with pytest.raises(ValueError, match="distinct"):
        MaxDiversification(stocks_symbol="SPY", bonds_symbol="SPY")


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["SPY", "TLT", "DBC"],
        dtype=float,
    )
    weights = MaxDiversification().generate_signals(empty)
    assert weights.empty


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        MaxDiversification().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_missing_required_symbols() -> None:
    prices = _gbm_panel(["SPY", "TLT"], years=2, drifts=(0.08, 0.03), vols=(0.16, 0.14))
    with pytest.raises(KeyError, match="DBC"):
        MaxDiversification().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=2,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
    )
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        MaxDiversification().generate_signals(prices)


# ---------------------------------------------------------------------------
# Economic behaviour: MDP weights via _covariance helper
# ---------------------------------------------------------------------------
def test_warmup_weights_are_zero() -> None:
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=2,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
    )
    weights = MaxDiversification(cov_window_days=252).generate_signals(prices)
    warmup = weights.iloc[:252]
    assert (warmup.to_numpy() == 0.0).all()


def test_weights_sum_to_one_after_warmup() -> None:
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
    )
    weights = MaxDiversification(cov_window_days=252).generate_signals(prices)
    mature = weights.iloc[280:]
    sums = mature.sum(axis=1)
    nonzero = sums > 1e-9
    if nonzero.any():
        np.testing.assert_allclose(sums[nonzero].to_numpy(), 1.0, atol=1e-6)


def test_weights_non_negative_after_warmup() -> None:
    """Long-only MDP: all weights >= 0."""
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
    )
    weights = MaxDiversification(cov_window_days=252).generate_signals(prices)
    mature = weights.iloc[280:]
    assert (mature.to_numpy() >= -1e-9).all()


def test_equal_correlation_equal_vol_produces_equal_weights() -> None:
    """When all assets have identical vol and pairwise correlation,
    MDP collapses to equal-weight (analytic anchor).

    Verifies the strategy's MDP solver consistently produces the
    equal-correlation-equal-vol equal-weight result documented in
    the _covariance helper's test_equal_correlation_equal_vol_equal_weight.
    """
    sigma = 0.15
    rho = 0.3
    correlations = np.array(
        [
            [1.0, rho, rho],
            [rho, 1.0, rho],
            [rho, rho, 1.0],
        ]
    )
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.0, 0.0, 0.0),
        vols=(sigma, sigma, sigma),
        correlations=correlations,
        seed=42,
    )
    weights = MaxDiversification(cov_window_days=252, shrinkage="none").generate_signals(prices)
    final = weights.iloc[-1].to_numpy()
    # MDP weights should be approximately equal-weight: 1/3 each.
    # Wide tolerance because the rolling sample cov has noise.
    np.testing.assert_allclose(final, np.full(3, 1.0 / 3.0), rtol=0.30)


def test_max_weight_cap_binds() -> None:
    """When max_weight is set low, the cap binds and weight is
    redistributed across the remaining assets."""
    # Asymmetric correlations to drive MDP weights away from equal.
    correlations = np.array(
        [
            [1.0, 0.05, 0.4],
            [0.05, 1.0, 0.1],
            [0.4, 0.1, 1.0],
        ]
    )
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.0, 0.0, 0.0),
        vols=(0.15, 0.10, 0.18),
        correlations=correlations,
        seed=42,
    )
    weights_uncapped = MaxDiversification(
        cov_window_days=252, shrinkage="none", max_weight=1.0
    ).generate_signals(prices)
    weights_capped = MaxDiversification(
        cov_window_days=252, shrinkage="none", max_weight=0.4
    ).generate_signals(prices)
    final_uncapped = weights_uncapped.iloc[-1]
    final_capped = weights_capped.iloc[-1]
    # Each weight in the capped version <= 0.4 + tolerance.
    assert (final_capped.to_numpy() <= 0.4 + 1e-6).all()
    # Capped weights sum to 1.0
    assert final_capped.sum() == pytest.approx(1.0, abs=1e-6)
    # The capped solution differs from the uncapped (the cap binds).
    assert not np.allclose(final_uncapped.to_numpy(), final_capped.to_numpy(), atol=1e-3)


def test_mdp_diversification_ratio_geq_equal_weight() -> None:
    """The MDP solution's diversification ratio is >= equal-weight DR.

    By construction, MDP is the maximum-DR portfolio under the
    long-only sum-to-1 constraint. Equal-weight is a feasible
    point in the constraint set, so MDP's DR must dominate.
    """
    # Asymmetric setup to produce a non-equal-weight MDP.
    correlations = np.array(
        [
            [1.0, 0.0, 0.5],
            [0.0, 1.0, 0.0],
            [0.5, 0.0, 1.0],
        ]
    )
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.0, 0.0, 0.0),
        vols=(0.15, 0.10, 0.18),
        correlations=correlations,
        seed=42,
    )
    weights = MaxDiversification(cov_window_days=252, shrinkage="none").generate_signals(prices)
    final = weights.iloc[-1].to_numpy()

    # Recompute the realised covariance at the final bar to evaluate DR.
    daily_log_returns = np.log(prices / prices.shift(1)).dropna()
    sample_cov = np.cov(daily_log_returns.iloc[-252:].to_numpy().T, ddof=1)

    dr_mdp = diversification_ratio(final, sample_cov)
    dr_equal = diversification_ratio(np.full(3, 1.0 / 3.0), sample_cov)
    assert dr_mdp >= dr_equal - 1e-3  # tolerate small SLSQP numerical noise


def test_deterministic_output() -> None:
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
        seed=42,
    )
    w1 = MaxDiversification().generate_signals(prices)
    w2 = MaxDiversification().generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)
