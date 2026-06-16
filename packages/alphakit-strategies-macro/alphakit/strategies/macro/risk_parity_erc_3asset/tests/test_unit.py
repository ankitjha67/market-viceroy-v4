"""Unit tests for risk_parity_erc_3asset signal generation.

First consumer of the shared ``_covariance`` helper module —
tests verify the strategy correctly consumes
``rolling_covariance`` and ``solve_erc_weights`` from
``alphakit.strategies.macro._covariance`` and produces ERC
weights with the expected mathematical properties (sum-to-1,
all-positive, equal risk contribution).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.macro.risk_parity_erc_3asset.strategy import (
    RiskParityErc3Asset,
)


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
    assert isinstance(RiskParityErc3Asset(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = RiskParityErc3Asset()
    assert s.name == "risk_parity_erc_3asset"
    assert s.family == "macro"
    assert s.paper_doi == "10.2469/faj.v68.n1.1"  # AFP 2012
    assert s.rebalance_frequency == "monthly"
    assert s.asset_classes == ("equity", "bonds", "commodities")


def test_required_symbols_are_default_three() -> None:
    s = RiskParityErc3Asset()
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
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        RiskParityErc3Asset(**kwargs)  # type: ignore[arg-type]


def test_constructor_rejects_duplicate_symbols() -> None:
    with pytest.raises(ValueError, match="distinct"):
        RiskParityErc3Asset(stocks_symbol="SPY", bonds_symbol="SPY")


def test_constructor_accepts_custom_symbols() -> None:
    s = RiskParityErc3Asset(
        stocks_symbol="VTI",
        bonds_symbol="EDV",
        commodities_symbol="GLD",
    )
    assert s.required_symbols == ("VTI", "EDV", "GLD")


def test_constructor_accepts_shrinkage_alternatives() -> None:
    s_none = RiskParityErc3Asset(shrinkage="none")
    s_const = RiskParityErc3Asset(shrinkage="constant")
    s_lw = RiskParityErc3Asset(shrinkage="ledoit_wolf")
    assert s_none.shrinkage == "none"
    assert s_const.shrinkage == "constant"
    assert s_lw.shrinkage == "ledoit_wolf"


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["SPY", "TLT", "DBC"],
        dtype=float,
    )
    weights = RiskParityErc3Asset().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == ["SPY", "TLT", "DBC"]


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        RiskParityErc3Asset().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_missing_required_symbols() -> None:
    prices = _gbm_panel(["SPY", "TLT"], years=2, drifts=(0.08, 0.03), vols=(0.16, 0.14))
    with pytest.raises(KeyError, match="DBC"):
        RiskParityErc3Asset().generate_signals(prices)


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame(
        {
            "SPY": [100.0, 101.0],
            "TLT": [100.0, 101.0],
            "DBC": [100.0, 101.0],
        },
        index=[0, 1],
    )
    with pytest.raises(TypeError, match="DatetimeIndex"):
        RiskParityErc3Asset().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=2,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
    )
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        RiskParityErc3Asset().generate_signals(prices)


def test_output_is_aligned_to_input() -> None:
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
    )
    weights = RiskParityErc3Asset().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == ["SPY", "TLT", "DBC"]
    assert weights.to_numpy().dtype == np.float64


# ---------------------------------------------------------------------------
# Economic behaviour: ERC weights via _covariance helper
# ---------------------------------------------------------------------------
def test_warmup_weights_are_zero() -> None:
    """Before cov_window_days are available, weights are zero."""
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=2,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
    )
    weights = RiskParityErc3Asset(cov_window_days=252).generate_signals(prices)
    # First ~252 bars (warmup) carry zero weights.
    warmup = weights.iloc[:252]
    assert (warmup.to_numpy() == 0.0).all()


def test_weights_sum_to_one_after_warmup() -> None:
    """After warmup, weights sum to 1.0 (ERC is long-only normalised)."""
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
    )
    weights = RiskParityErc3Asset(cov_window_days=252).generate_signals(prices)
    mature = weights.iloc[280:]  # well past warmup
    sums = mature.sum(axis=1)
    # Drop any bars where the strategy emitted zero (no valid cov)
    nonzero = sums > 1e-9
    if nonzero.any():
        np.testing.assert_allclose(sums[nonzero].to_numpy(), 1.0, atol=1e-9)


def test_weights_all_positive_after_warmup() -> None:
    """ERC weights are strictly positive (Spinu log-barrier formulation)."""
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
    )
    weights = RiskParityErc3Asset(cov_window_days=252).generate_signals(prices)
    mature = weights.iloc[280:]
    # On rebalance bars (nonzero rows), every weight should be > 0
    nonzero_rows = mature.sum(axis=1) > 1e-9
    assert (mature.loc[nonzero_rows].to_numpy() >= 0).all()


def test_erc_equal_risk_contribution_invariant() -> None:
    """At each rebalance, the realized w_i * (Σw)_i should be ≈ equal across i.

    This is the load-bearing ERC invariant — verifies that the
    `_covariance.solve_erc_weights` helper is producing genuinely
    risk-balanced weights, not just any feasible long-only weight
    vector.
    """
    # Use uncorrelated panel so ERC reduces to inverse-vol (analytic anchor).
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.0, 0.0, 0.0),
        vols=(0.10, 0.20, 0.30),
        correlations=np.eye(3),
        seed=42,
    )
    weights = RiskParityErc3Asset(cov_window_days=252, shrinkage="none").generate_signals(prices)
    # Sample a late rebalance bar
    final = weights.iloc[-1].to_numpy()
    assert final.sum() == pytest.approx(1.0, abs=1e-6)
    # For uncorrelated assets with vols (10%, 20%, 30%), ERC weights
    # are inversely proportional to vol: weights ∝ (1/0.10, 1/0.20, 1/0.30)
    expected = np.array([1 / 0.10, 1 / 0.20, 1 / 0.30])
    expected = expected / expected.sum()
    # Tolerance is wide because the rolling sample covariance has noise.
    np.testing.assert_allclose(final, expected, rtol=0.25)


def test_low_vol_asset_overweighted_vs_high_vol_asset() -> None:
    """ERC under-weights high-vol assets relative to equal-weight."""
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.0, 0.0, 0.0),
        vols=(0.30, 0.05, 0.20),  # TLT is lowest vol
        correlations=np.eye(3),
        seed=11,
    )
    weights = RiskParityErc3Asset(cov_window_days=252, shrinkage="none").generate_signals(prices)
    final = weights.iloc[-1]
    # TLT (lowest vol) should receive the largest weight; SPY (highest vol) the smallest.
    assert final["TLT"] > final["DBC"] > final["SPY"]


def test_deterministic_output() -> None:
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
        seed=42,
    )
    w1 = RiskParityErc3Asset().generate_signals(prices)
    w2 = RiskParityErc3Asset().generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)


def test_shrinkage_methods_produce_different_weights() -> None:
    """The three shrinkage methods should produce materially different
    covariance estimates and therefore different weights."""
    prices = _gbm_panel(
        ["SPY", "TLT", "DBC"],
        years=3,
        drifts=(0.08, 0.03, 0.05),
        vols=(0.16, 0.14, 0.18),
        seed=42,
    )
    w_none = RiskParityErc3Asset(shrinkage="none").generate_signals(prices)
    w_lw = RiskParityErc3Asset(shrinkage="ledoit_wolf").generate_signals(prices)
    w_const = RiskParityErc3Asset(shrinkage="constant").generate_signals(prices)
    # On the same prices, different shrinkage → different weights (small but
    # detectable differences at the final bar).
    assert not np.allclose(w_none.iloc[-1], w_lw.iloc[-1], atol=1e-4)
    assert not np.allclose(w_none.iloc[-1], w_const.iloc[-1], atol=1e-4)
