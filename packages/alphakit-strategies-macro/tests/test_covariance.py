"""Tests for :mod:`alphakit.strategies.macro._covariance`.

Three Session 2G strategies (``risk_parity_erc_3asset``,
``min_variance_gtaa``, ``max_diversification``) depend on this shared
helper. Comprehensive coverage here is the gate-3 review surface for
the architectural primitive — failures would propagate to all three
dependent strategies.

Test groups:

1. ``rolling_covariance`` — shape, indexing, NaN handling, window
   semantics, shrinkage method selection.
2. Ledoit-Wolf shrinkage — alpha bounded in ``[0, 1]``, convergence
   behaviour with known inputs, singular-covariance fallback.
3. ERC solver — analytic case (3 uncorrelated assets with known
   inverse-vol weights), weight-sum and positivity invariants,
   equal-risk-contribution invariant.
4. Minimum-variance solver — analytic 2-asset case (Markowitz
   closed-form), long-only constraint, weight-sum invariant.
5. Diversification ratio — single-asset case, hand-checked 2-asset
   case, maximum-diversification analytic case (equal correlation).
6. Edge cases — N=1, N=2, N=10.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.strategies.macro._covariance import (
    _ledoit_wolf_shrinkage,
    diversification_ratio,
    rolling_covariance,
    solve_erc_weights,
    solve_max_diversification_weights,
    solve_min_variance_weights,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _gaussian_returns(
    n_obs: int, n_assets: int, vols: np.ndarray, corr: np.ndarray, seed: int = 7
) -> np.ndarray:
    """Generate (n_obs, n_assets) Gaussian returns with given vols & corr."""
    rng = np.random.default_rng(seed)
    sigma = np.outer(vols, vols) * corr
    return rng.multivariate_normal(np.zeros(n_assets), sigma, size=n_obs)


@pytest.fixture
def three_uncorrelated_returns() -> pd.DataFrame:
    """500 obs of 3 uncorrelated Gaussian returns with vols 1%/2%/3%."""
    vols = np.array([0.01, 0.02, 0.03])
    corr = np.eye(3)
    arr = _gaussian_returns(500, 3, vols, corr, seed=42)
    return pd.DataFrame(
        arr,
        index=pd.date_range("2020-01-01", periods=500, freq="B"),
        columns=["A", "B", "C"],
    )


@pytest.fixture
def four_correlated_returns() -> pd.DataFrame:
    """500 obs of 4 correlated returns: equity-block (high corr) + bonds."""
    vols = np.array([0.012, 0.013, 0.011, 0.006])
    corr = np.array(
        [
            [1.00, 0.85, 0.80, -0.10],
            [0.85, 1.00, 0.78, -0.08],
            [0.80, 0.78, 1.00, -0.05],
            [-0.10, -0.08, -0.05, 1.00],
        ]
    )
    arr = _gaussian_returns(500, 4, vols, corr, seed=13)
    return pd.DataFrame(
        arr,
        index=pd.date_range("2020-01-01", periods=500, freq="B"),
        columns=["SPY", "EFA", "EEM", "AGG"],
    )


# ---------------------------------------------------------------------------
# rolling_covariance
# ---------------------------------------------------------------------------


class TestRollingCovariance:
    def test_shape_and_index(self, three_uncorrelated_returns: pd.DataFrame) -> None:
        cov = rolling_covariance(three_uncorrelated_returns, window=100, shrinkage="none")
        # 500 obs - 100 window + 1 = 401 valid dates × 3 assets per date
        expected_dates = 500 - 100 + 1
        assert len(cov.index.unique(level="date")) == expected_dates
        assert cov.index.names == ["date", "asset"]
        assert list(cov.columns) == ["A", "B", "C"]

    def test_slice_is_square_and_symmetric(self, three_uncorrelated_returns: pd.DataFrame) -> None:
        cov = rolling_covariance(three_uncorrelated_returns, window=100, shrinkage="none")
        t = cov.index.get_level_values("date")[100]
        matrix = cov.loc[t]
        assert matrix.shape == (3, 3)
        np.testing.assert_allclose(matrix.to_numpy(), matrix.to_numpy().T, atol=1e-12)

    def test_recovers_known_variances_uncorrelated(
        self, three_uncorrelated_returns: pd.DataFrame
    ) -> None:
        cov = rolling_covariance(three_uncorrelated_returns, window=400, shrinkage="none")
        t = cov.index.get_level_values("date").max()
        matrix = cov.loc[t].to_numpy()
        # diagonal ≈ vols² = [1e-4, 4e-4, 9e-4]; off-diagonal correlations
        # should be near zero. With 400 samples of "uncorrelated" Gaussians
        # the sample correlation has stddev ≈ 1/sqrt(400) = 0.05, so a 3σ
        # tolerance allows |corr| < 0.15.
        np.testing.assert_allclose(np.diag(matrix), [1e-4, 4e-4, 9e-4], rtol=0.25)
        vols = np.sqrt(np.diag(matrix))
        sample_corr = matrix / np.outer(vols, vols)
        off_diag_corr = sample_corr - np.diag(np.diag(sample_corr))
        assert np.abs(off_diag_corr).max() < 0.15

    def test_window_too_small_returns_empty(self) -> None:
        df = pd.DataFrame(
            np.random.default_rng(0).normal(0, 0.01, size=(50, 2)),
            index=pd.date_range("2020-01-01", periods=50, freq="B"),
            columns=["A", "B"],
        )
        cov = rolling_covariance(df, window=100, shrinkage="none")
        assert len(cov) == 0
        assert cov.index.names == ["date", "asset"]
        assert list(cov.columns) == ["A", "B"]

    def test_nan_rows_skipped_within_window(self, three_uncorrelated_returns: pd.DataFrame) -> None:
        df = three_uncorrelated_returns.copy()
        # Drop a single row in the middle to NaN — should still produce valid output
        df.iloc[100, 0] = np.nan
        cov = rolling_covariance(df, window=100, shrinkage="none")
        assert len(cov) > 0
        # Latest cov should still be finite
        t = cov.index.get_level_values("date").max()
        assert np.isfinite(cov.loc[t].to_numpy()).all()

    def test_majority_nan_window_omitted(self) -> None:
        df = pd.DataFrame(
            np.random.default_rng(0).normal(0, 0.01, size=(200, 2)),
            index=pd.date_range("2020-01-01", periods=200, freq="B"),
            columns=["A", "B"],
        )
        df.iloc[:90, 0] = np.nan  # 90 of first 100 rows NaN in column A
        cov = rolling_covariance(df, window=100, shrinkage="none")
        # The first window-end date (index 99) should be omitted because
        # only 10 of 100 rows are valid (< 100//2).
        dates = cov.index.unique(level="date")
        assert df.index[99] not in dates

    def test_ledoit_wolf_default_shrinkage(self, four_correlated_returns: pd.DataFrame) -> None:
        cov_lw = rolling_covariance(four_correlated_returns, window=120, shrinkage="ledoit_wolf")
        cov_none = rolling_covariance(four_correlated_returns, window=120, shrinkage="none")
        t = cov_lw.index.get_level_values("date").max()
        m_lw = cov_lw.loc[t].to_numpy()
        m_none = cov_none.loc[t].to_numpy()
        # Shrinkage should pull off-diagonal correlations toward the
        # average pairwise correlation; the matrices should differ
        # but both be symmetric and positive-definite.
        assert not np.allclose(m_lw, m_none)
        np.testing.assert_allclose(m_lw, m_lw.T, atol=1e-12)
        eigvals = np.linalg.eigvalsh(m_lw)
        assert (eigvals > 0).all()

    def test_constant_shrinkage_smokes(self, four_correlated_returns: pd.DataFrame) -> None:
        cov = rolling_covariance(four_correlated_returns, window=120, shrinkage="constant")
        assert len(cov) > 0
        t = cov.index.get_level_values("date").max()
        matrix = cov.loc[t].to_numpy()
        eigvals = np.linalg.eigvalsh(matrix)
        assert (eigvals > 0).all()

    def test_invalid_window_raises(self, three_uncorrelated_returns: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="window must be >= 2"):
            rolling_covariance(three_uncorrelated_returns, window=1)

    def test_invalid_shrinkage_raises(self, three_uncorrelated_returns: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="shrinkage must be"):
            rolling_covariance(
                three_uncorrelated_returns,
                window=100,
                shrinkage="bogus",  # type: ignore[arg-type]
            )

    def test_single_asset_raises(self) -> None:
        df = pd.DataFrame(
            np.random.default_rng(0).normal(0, 0.01, size=(200, 1)),
            index=pd.date_range("2020-01-01", periods=200, freq="B"),
            columns=["A"],
        )
        with pytest.raises(ValueError, match="requires >= 2 assets"):
            rolling_covariance(df, window=100)


# ---------------------------------------------------------------------------
# Ledoit-Wolf shrinkage
# ---------------------------------------------------------------------------


class TestLedoitWolfShrinkage:
    def test_alpha_in_unit_interval(self) -> None:
        rng = np.random.default_rng(0)
        x = rng.normal(0, 0.01, size=(500, 5))
        x = x - x.mean(axis=0)
        _, alpha = _ledoit_wolf_shrinkage(x)
        assert 0.0 <= alpha <= 1.0

    def test_high_n_low_t_pushes_alpha_higher(self) -> None:
        """As effective sample size shrinks, shrinkage intensity grows."""
        rng = np.random.default_rng(0)
        x_big = rng.normal(0, 0.01, size=(2000, 5))
        x_big = x_big - x_big.mean(axis=0)
        _, alpha_big = _ledoit_wolf_shrinkage(x_big)

        x_small = rng.normal(0, 0.01, size=(30, 5))
        x_small = x_small - x_small.mean(axis=0)
        _, alpha_small = _ledoit_wolf_shrinkage(x_small)

        # Small sample → more shrinkage
        assert alpha_small > alpha_big

    def test_returns_symmetric_pd(self) -> None:
        rng = np.random.default_rng(0)
        x = rng.normal(0, 0.01, size=(300, 6))
        x = x - x.mean(axis=0)
        cov, _ = _ledoit_wolf_shrinkage(x)
        np.testing.assert_allclose(cov, cov.T, atol=1e-12)
        assert (np.linalg.eigvalsh(cov) > 0).all()

    def test_single_asset_raises(self) -> None:
        rng = np.random.default_rng(0)
        x = rng.normal(0, 0.01, size=(100, 1))
        x = x - x.mean(axis=0)
        with pytest.raises(ValueError, match="requires T>=2 and N>=2"):
            _ledoit_wolf_shrinkage(x)

    def test_singular_covariance_fallback_via_rolling(self) -> None:
        """N >= T degenerate case must not crash rolling_covariance."""
        rng = np.random.default_rng(0)
        # 30 obs, 8 assets, window=10 → some windows have T_eff < N
        df = pd.DataFrame(
            rng.normal(0, 0.01, size=(30, 8)),
            index=pd.date_range("2020-01-01", periods=30, freq="B"),
            columns=[f"A{i}" for i in range(8)],
        )
        # Window 10 < 8 assets; falls back to np.cov instead of LW.
        cov = rolling_covariance(df, window=10, shrinkage="ledoit_wolf")
        assert len(cov) > 0
        for t in cov.index.unique(level="date"):
            matrix = cov.loc[t].to_numpy()
            assert np.isfinite(matrix).all()


# ---------------------------------------------------------------------------
# ERC solver
# ---------------------------------------------------------------------------


class TestSolveErcWeights:
    def test_uncorrelated_three_assets_inverse_vol(self) -> None:
        """ERC on 3 uncorrelated assets reduces to inverse-volatility weights.

        For diagonal Σ = diag(σ₁², σ₂², σ₃²), the ERC condition
        w_i²σ_i² = const gives w_i ∝ 1/σ_i.
        """
        vols = np.array([0.10, 0.20, 0.30])
        cov = np.diag(vols**2)
        w = solve_erc_weights(cov)
        expected = (1.0 / vols) / (1.0 / vols).sum()
        np.testing.assert_allclose(w, expected, atol=1e-5)

    def test_weights_sum_to_one(self) -> None:
        cov = np.array([[0.04, 0.02, 0.00], [0.02, 0.09, 0.01], [0.00, 0.01, 0.16]])
        w = solve_erc_weights(cov)
        assert w.sum() == pytest.approx(1.0, abs=1e-8)

    def test_weights_all_positive(self) -> None:
        rng = np.random.default_rng(0)
        x = rng.normal(0, 0.01, size=(500, 5))
        sample = np.cov(x.T, ddof=1)
        w = solve_erc_weights(sample)
        assert (w > 0).all()

    def test_equal_risk_contribution_invariant(self) -> None:
        """At optimum, w_i * (Σw)_i is constant across all i.

        Verifies the algebraic ERC invariant on a 4-asset non-diagonal
        covariance with mixed positive/negative off-diagonal entries.
        Mathematically equivalent to the canonical
        ``RC_i = w_i * (Σw)_i / σ_p`` formulation (σ_p is a common
        scalar across all i; equality of ``w_i * (Σw)_i`` implies
        equality of RC_i). The explicit RC-formula variant lives in
        ``test_erc_equal_risk_contribution_on_correlated_assets``.
        """
        cov = np.array(
            [
                [0.04, 0.02, 0.005, -0.001],
                [0.02, 0.09, 0.010, 0.000],
                [0.005, 0.010, 0.16, 0.002],
                [-0.001, 0.000, 0.002, 0.0025],
            ]
        )
        w = solve_erc_weights(cov)
        sigma_w = cov @ w
        contributions = w * sigma_w
        # All contributions equal within tolerance
        np.testing.assert_allclose(contributions, contributions.mean(), rtol=1e-4)

    def test_erc_equal_risk_contribution_on_correlated_assets(self) -> None:
        """Solved weights produce equal risk contribution under positive corr.

        Canonical RC formula:
            MRC_i = (Σ w)_i / sqrt(wᵀ Σ w)
            RC_i  = w_i * MRC_i
        ERC requires ``RC_i = portfolio_vol / N`` for all i. Sibling of
        ``test_equal_risk_contribution_invariant``; this version is the
        gate-3 review surface using the textbook RC normalization.
        """
        vols = np.array([0.10, 0.20, 0.30])
        corr = np.array(
            [
                [1.0, 0.5, 0.3],
                [0.5, 1.0, 0.4],
                [0.3, 0.4, 1.0],
            ]
        )
        cov = np.outer(vols, vols) * corr
        w = solve_erc_weights(cov)
        portfolio_vol = float(np.sqrt(w @ cov @ w))
        marginal_rc = (cov @ w) / portfolio_vol
        risk_contributions = w * marginal_rc
        expected_rc = portfolio_vol / len(w)
        np.testing.assert_allclose(risk_contributions, expected_rc, rtol=1e-4)

    def test_n_eq_1_returns_full_weight(self) -> None:
        w = solve_erc_weights(np.array([[0.04]]))
        np.testing.assert_array_equal(w, np.array([1.0]))

    def test_zero_variance_raises(self) -> None:
        cov = np.array([[0.04, 0.0], [0.0, 0.0]])
        with pytest.raises(ValueError, match="positive variance"):
            solve_erc_weights(cov)

    def test_non_square_raises(self) -> None:
        with pytest.raises(ValueError, match="square 2D"):
            solve_erc_weights(np.zeros((3, 2)))


# ---------------------------------------------------------------------------
# Minimum-variance solver
# ---------------------------------------------------------------------------


class TestSolveMinVarianceWeights:
    def test_two_asset_uncorrelated_markowitz_closed_form(self) -> None:
        """For uncorrelated 2-asset case: w_1 = σ_2² / (σ_1² + σ_2²)."""
        sigma1, sigma2 = 0.10, 0.20
        cov = np.diag([sigma1**2, sigma2**2])
        w = solve_min_variance_weights(cov, long_only=True)
        expected_w1 = sigma2**2 / (sigma1**2 + sigma2**2)
        expected = np.array([expected_w1, 1.0 - expected_w1])
        np.testing.assert_allclose(w, expected, atol=1e-6)

    def test_two_asset_correlated_markowitz_closed_form(self) -> None:
        """ρ=0.5, equal vols: w_1 = w_2 = 0.5."""
        sigma = 0.15
        rho = 0.5
        cov = np.array([[sigma**2, rho * sigma**2], [rho * sigma**2, sigma**2]])
        w = solve_min_variance_weights(cov, long_only=True)
        np.testing.assert_allclose(w, np.array([0.5, 0.5]), atol=1e-6)

    def test_weights_sum_to_one(self) -> None:
        cov = np.array([[0.04, 0.02], [0.02, 0.09]])
        w = solve_min_variance_weights(cov)
        assert w.sum() == pytest.approx(1.0, abs=1e-8)

    def test_long_only_constraint_binds(self) -> None:
        """When unconstrained min-var has a negative weight, long-only clips it.

        3 assets where asset 3 has very high vol and positive correlation
        with asset 2 — the unconstrained solution should short asset 2 or 3,
        but long-only forces both >= 0.
        """
        cov = np.array(
            [
                [0.0036, 0.000, 0.000],
                [0.000, 0.0100, 0.0095],
                [0.000, 0.0095, 0.0100],
            ]
        )
        w = solve_min_variance_weights(cov, long_only=True)
        assert (w >= -1e-9).all()
        assert w.sum() == pytest.approx(1.0, abs=1e-6)
        # The lowest-variance asset (idx 0, var=0.0036) should dominate
        assert w[0] > w[1]
        assert w[0] > w[2]

    def test_long_short_allows_negative_weights(self) -> None:
        cov = np.array(
            [
                [0.0036, 0.000, 0.000],
                [0.000, 0.0100, 0.0095],
                [0.000, 0.0095, 0.0100],
            ]
        )
        w_long = solve_min_variance_weights(cov, long_only=True)
        w_ls = solve_min_variance_weights(cov, long_only=False)
        assert w_ls.sum() == pytest.approx(1.0, abs=1e-6)
        # Long-short solution should have lower variance than long-only
        assert w_ls @ cov @ w_ls <= w_long @ cov @ w_long + 1e-10

    def test_min_variance_long_only_constraint_binds(self) -> None:
        """When unconstrained MV would short an asset, long-only drops it to 0.

        Textbook construction for an unconstrained short: a high-vol
        asset positively correlated with a low-vol asset. Shorting the
        high-vol asset becomes a partial hedge against the low-vol
        asset's exposure, reducing total portfolio variance. The
        long-only constraint must force ``w_high_vol = 0`` and rebalance
        the remaining weight.

        (Note: the inverse intuition — low-vol + negative correlation —
        does NOT trigger a short; that construction gives the low-vol
        asset a *high positive* weight because it is a desirable hedge.
        The unconstrained-short condition requires
        ``ρ_ij * σ_j > σ_i`` for some i, which is the high-vol
        positively-correlated-with-low-vol pattern, not the reverse.)
        """
        vols = np.array([0.50, 0.10, 0.20])
        corr = np.array(
            [
                [1.00, 0.90, 0.00],
                [0.90, 1.00, 0.00],
                [0.00, 0.00, 1.00],
            ]
        )
        cov = np.outer(vols, vols) * corr

        w_unconstrained = solve_min_variance_weights(cov, long_only=False)
        # Confirm the construction: unconstrained MV shorts asset 0
        assert w_unconstrained[0] < 0

        w_constrained = solve_min_variance_weights(cov, long_only=True)
        # Long-only forces asset 0 weight to (numerically) zero
        assert w_constrained[0] < 1e-6
        # Constraint solution still sums to 1.0
        assert w_constrained.sum() == pytest.approx(1.0, abs=1e-6)
        # All weights non-negative
        assert (w_constrained >= -1e-9).all()
        # Rebalanced weight goes to the unhedged assets (1 and 2)
        assert w_constrained[1] + w_constrained[2] == pytest.approx(1.0, abs=1e-6)

    def test_n_eq_1_returns_full_weight(self) -> None:
        w = solve_min_variance_weights(np.array([[0.04]]))
        np.testing.assert_array_equal(w, np.array([1.0]))

    def test_invalid_max_weight_raises(self) -> None:
        with pytest.raises(ValueError, match="max_weight must be"):
            solve_min_variance_weights(np.eye(3) * 0.01, max_weight=0.0)


# ---------------------------------------------------------------------------
# Diversification ratio + max-diversification solver
# ---------------------------------------------------------------------------


class TestDiversificationRatio:
    def test_single_asset_dr_is_one(self) -> None:
        dr = diversification_ratio(np.array([1.0]), np.array([[0.04]]))
        assert dr == pytest.approx(1.0, abs=1e-12)

    def test_two_asset_hand_check(self) -> None:
        """Equal-weight 2 assets with σ=0.1 each, ρ=0.5.

        wᵀσ = 0.5*0.1 + 0.5*0.1 = 0.1
        wᵀΣw = 0.25*0.01 + 0.25*0.01 + 2*0.25*0.5*0.01 = 0.0075
        DR = 0.1 / sqrt(0.0075) ≈ 1.1547
        """
        cov = np.array([[0.01, 0.005], [0.005, 0.01]])
        w = np.array([0.5, 0.5])
        dr = diversification_ratio(w, cov)
        assert dr == pytest.approx(0.1 / np.sqrt(0.0075), abs=1e-10)

    def test_zero_variance_returns_zero(self) -> None:
        cov = np.zeros((2, 2))
        dr = diversification_ratio(np.array([0.5, 0.5]), cov)
        assert dr == 0.0


class TestSolveMaxDiversificationWeights:
    def test_equal_correlation_equal_vol_equal_weight(self) -> None:
        """When all pairs have equal correlation and equal vol, MDP is equal-weight.

        With identical vols and identical pairwise correlations, the
        diversification ratio is symmetric in the weights and the
        maximiser is the equal-weight portfolio.
        """
        n = 4
        sigma = 0.15
        rho = 0.3
        cov = np.full((n, n), rho * sigma**2)
        np.fill_diagonal(cov, sigma**2)
        w = solve_max_diversification_weights(cov, long_only=True)
        np.testing.assert_allclose(w, np.full(n, 1.0 / n), atol=1e-5)

    def test_higher_dr_than_equal_weight_in_mixed_universe(self) -> None:
        """In a non-symmetric universe, MDP should achieve DR > equal-weight."""
        cov = np.array(
            [
                [0.0144, 0.0090, 0.0080, -0.0010],
                [0.0090, 0.0169, 0.0085, -0.0008],
                [0.0080, 0.0085, 0.0121, -0.0005],
                [-0.0010, -0.0008, -0.0005, 0.0036],
            ]
        )
        w_mdp = solve_max_diversification_weights(cov, long_only=True)
        w_eq = np.full(4, 0.25)
        assert diversification_ratio(w_mdp, cov) > diversification_ratio(w_eq, cov)

    def test_weights_sum_to_one(self) -> None:
        cov = np.array([[0.04, 0.02], [0.02, 0.09]])
        w = solve_max_diversification_weights(cov)
        assert w.sum() == pytest.approx(1.0, abs=1e-8)

    def test_long_only_no_negatives(self) -> None:
        cov = np.array(
            [
                [0.0036, 0.000, 0.000],
                [0.000, 0.0100, 0.0095],
                [0.000, 0.0095, 0.0100],
            ]
        )
        w = solve_max_diversification_weights(cov, long_only=True)
        assert (w >= -1e-9).all()

    def test_n_eq_1_returns_full_weight(self) -> None:
        w = solve_max_diversification_weights(np.array([[0.04]]))
        np.testing.assert_array_equal(w, np.array([1.0]))


# ---------------------------------------------------------------------------
# Cross-solver sanity (N=10, all three converge)
# ---------------------------------------------------------------------------


class TestEdgeCaseN10:
    def test_all_three_solvers_converge_on_n_eq_10(self) -> None:
        rng = np.random.default_rng(123)
        # Random PSD covariance: A Aᵀ + small ridge
        a = rng.normal(0, 0.05, size=(10, 12))
        cov = a @ a.T + 1e-6 * np.eye(10)

        w_erc = solve_erc_weights(cov)
        w_mv = solve_min_variance_weights(cov, long_only=True)
        w_mdp = solve_max_diversification_weights(cov, long_only=True)

        for w in (w_erc, w_mv, w_mdp):
            assert w.shape == (10,)
            assert w.sum() == pytest.approx(1.0, abs=1e-6)
            assert (w >= -1e-9).all()

        # Sanity: the three solvers solve different optimisation problems
        # and on a non-degenerate covariance must produce distinct weights.
        # If any two collapse to the same vector, the implementations have
        # a bug or the test input has degenerated.
        assert not np.allclose(w_erc, w_mv, atol=1e-3)
        assert not np.allclose(w_erc, w_mdp, atol=1e-3)
        assert not np.allclose(w_mv, w_mdp, atol=1e-3)
