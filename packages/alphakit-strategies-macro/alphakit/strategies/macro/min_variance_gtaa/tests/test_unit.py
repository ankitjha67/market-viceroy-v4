"""Unit tests for min_variance_gtaa signal generation.

Second consumer of the shared ``_covariance`` helper module —
tests verify the strategy correctly consumes
``rolling_covariance`` and ``solve_min_variance_weights`` and
produces long-only MV weights with the expected mathematical
properties (sum-to-1, non-negative, lowest-vol-asset
concentration, binding-constraint behaviour).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.macro.min_variance_gtaa.strategy import MinVarianceGtaa


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
    assert isinstance(MinVarianceGtaa(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = MinVarianceGtaa()
    assert s.name == "min_variance_gtaa"
    assert s.family == "macro"
    assert s.paper_doi == "10.3905/jpm.1991.409335"  # Haugen & Baker 1991
    assert s.rebalance_frequency == "monthly"
    assert s.asset_classes == ("equity", "bonds", "commodities")


def test_required_symbols_are_default_three() -> None:
    s = MinVarianceGtaa()
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
        MinVarianceGtaa(**kwargs)  # type: ignore[arg-type]


def test_constructor_rejects_duplicate_symbols() -> None:
    with pytest.raises(ValueError, match="distinct"):
        MinVarianceGtaa(stocks_symbol="SPY", bonds_symbol="SPY")


def test_constructor_accepts_custom_max_weight() -> None:
    s = MinVarianceGtaa(max_weight=0.5)
    assert s.max_weight == 0.5


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["SPY", "TLT", "DBC"],
        dtype=float,
    )
    weights = MinVarianceGtaa().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == ["SPY", "TLT", "DBC"]


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        MinVarianceGtaa().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_missing_required_symbols() -> None:
    prices = _gbm_panel(["SPY", "TLT"], years=2, drifts=(0.08, 0.03), vols=(0.16, 0.14))
    with pytest.raises(KeyError, match="DBC"):
        MinVarianceGtaa().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=2,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
    )
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        MinVarianceGtaa().generate_signals(prices)


def test_output_is_aligned_to_input() -> None:
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
    )
    weights = MinVarianceGtaa().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == ["SPY", "TLT", "DBC"]


# ---------------------------------------------------------------------------
# Economic behaviour: MV weights via _covariance helper
# ---------------------------------------------------------------------------
def test_warmup_weights_are_zero() -> None:
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=2,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
    )
    weights = MinVarianceGtaa(cov_window_days=252).generate_signals(prices)
    warmup = weights.iloc[:252]
    assert (warmup.to_numpy() == 0.0).all()


def test_weights_sum_to_one_after_warmup() -> None:
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
    )
    weights = MinVarianceGtaa(cov_window_days=252).generate_signals(prices)
    mature = weights.iloc[280:]
    sums = mature.sum(axis=1)
    nonzero = sums > 1e-9
    if nonzero.any():
        np.testing.assert_allclose(sums[nonzero].to_numpy(), 1.0, atol=1e-6)


def test_weights_non_negative_after_warmup() -> None:
    """Long-only MV: all weights >= 0."""
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
    )
    weights = MinVarianceGtaa(cov_window_days=252).generate_signals(prices)
    mature = weights.iloc[280:]
    assert (mature.to_numpy() >= -1e-9).all()


def test_mv_overweights_lowest_vol_asset() -> None:
    """MV concentrates weight in the lowest-vol asset.

    With uncorrelated returns and vols (10%, 5%, 20%), the
    analytic long-only MV solution puts most weight on the
    lowest-vol asset (TLT in our universe with vol 5%).
    """
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.0, 0.0, 0.0),
        vols=(0.10, 0.05, 0.20),  # TLT lowest vol
        correlations=np.eye(3),
        seed=42,
    )
    weights = MinVarianceGtaa(cov_window_days=252, shrinkage="none").generate_signals(prices)
    final = weights.iloc[-1]
    # TLT should have the largest weight; DBC the smallest.
    assert final["TLT"] > final["SPY"] > final["DBC"]
    # TLT weight should dominate (>= 50% for these vol levels).
    assert final["TLT"] >= 0.5


def test_max_weight_cap_binds() -> None:
    """When max_weight is set low, the cap binds on the
    lowest-vol asset and weight is redistributed."""
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.0, 0.0, 0.0),
        vols=(0.10, 0.05, 0.20),
        correlations=np.eye(3),
        seed=42,
    )
    # Without cap: TLT typically gets 0.7+
    weights_uncapped = MinVarianceGtaa(
        cov_window_days=252, shrinkage="none", max_weight=1.0
    ).generate_signals(prices)
    # With cap at 0.4: TLT is bounded
    weights_capped = MinVarianceGtaa(
        cov_window_days=252, shrinkage="none", max_weight=0.4
    ).generate_signals(prices)

    final_uncapped = weights_uncapped.iloc[-1]
    final_capped = weights_capped.iloc[-1]
    # Cap binds: capped TLT <= 0.4 + tolerance
    assert final_capped["TLT"] <= 0.4 + 1e-6
    # And capped TLT < uncapped TLT (because cap reduces it)
    assert final_capped["TLT"] < final_uncapped["TLT"]


def test_three_asset_uncorrelated_inverse_vol_squared() -> None:
    """For 3 uncorrelated assets, the analytic long-only MV solution is
    w_i ∝ 1/σ_i² (inverse-variance weighting).

    With vols (10%, 5%, 20%) uncorrelated, the weights should be
    proportional to (1/0.01, 1/0.0025, 1/0.04) = (100, 400, 25) →
    normalised (~0.190, ~0.762, ~0.048).
    """
    vols = np.array([0.10, 0.05, 0.20])
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.0, 0.0, 0.0),
        vols=tuple(vols.tolist()),
        correlations=np.eye(3),
        seed=11,
    )
    weights = MinVarianceGtaa(cov_window_days=252, shrinkage="none").generate_signals(prices)
    final = weights.iloc[-1].to_numpy()
    expected = (1.0 / vols**2) / (1.0 / vols**2).sum()
    # Wide tolerance because the rolling sample covariance has noise
    # (sample vols deviate ~10% from true vols on a 252-day window).
    np.testing.assert_allclose(final, expected, rtol=0.30)


def test_deterministic_output() -> None:
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
        seed=42,
    )
    w1 = MinVarianceGtaa().generate_signals(prices)
    w2 = MinVarianceGtaa().generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)
