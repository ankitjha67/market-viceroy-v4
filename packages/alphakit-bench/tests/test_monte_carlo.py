"""Unit tests for the Monte-Carlo bootstrap (seeded, deterministic)."""

from __future__ import annotations

import numpy as np
import pytest
from alphakit.bench.validation.monte_carlo import bootstrap_sharpe


def _rng() -> np.random.Generator:
    return np.random.default_rng(42)


def test_strong_positive_has_positive_ci_and_low_pvalue() -> None:
    # A consistent positive drift with low noise -> Sharpe CI well above 0.
    returns = np.full(252, 0.01) + np.random.default_rng(0).normal(0, 0.002, 252)
    result = bootstrap_sharpe(returns, rng=_rng(), n_resamples=500)
    assert result.sharpe > 0
    assert result.ci_low > 0
    assert result.p_value < 0.05


def test_zero_mean_noise_straddles_zero() -> None:
    # Demean so the *sample* mean is exactly 0 (a finite noise draw otherwise
    # has its own non-zero mean); the bootstrap CI then straddles zero.
    noise = np.random.default_rng(7).normal(0.0, 0.01, 500)
    returns = noise - noise.mean()
    result = bootstrap_sharpe(returns, rng=_rng(), n_resamples=500)
    assert result.ci_low < 0 < result.ci_high
    assert 0.3 < result.p_value < 0.7


def test_deterministic_with_seed() -> None:
    returns = np.random.default_rng(1).normal(0.001, 0.01, 300)
    a = bootstrap_sharpe(returns, rng=np.random.default_rng(99), n_resamples=200)
    b = bootstrap_sharpe(returns, rng=np.random.default_rng(99), n_resamples=200)
    assert a == b


def test_block_bootstrap_runs() -> None:
    returns = np.random.default_rng(3).normal(0.0005, 0.01, 400)
    result = bootstrap_sharpe(returns, rng=_rng(), n_resamples=200, block_size=20)
    assert result.n_resamples == 200
    assert result.ci_low <= result.ci_high


def test_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        bootstrap_sharpe(np.array([0.01]), rng=_rng())
    with pytest.raises(ValueError, match="block_size"):
        bootstrap_sharpe(np.zeros(10), rng=_rng(), block_size=20)
    with pytest.raises(ValueError, match="n_resamples"):
        bootstrap_sharpe(np.zeros(10), rng=_rng(), n_resamples=0)
