"""Unit tests for the deflated/probabilistic Sharpe (pure, no scipy)."""

from __future__ import annotations

import math

import pytest
from alphakit.bench.validation.deflated_sharpe import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)


def test_psr_increases_with_sharpe() -> None:
    weak = probabilistic_sharpe_ratio(0.02, 252)
    strong = probabilistic_sharpe_ratio(0.20, 252)
    assert 0.0 <= weak <= 1.0
    assert strong > weak


def test_psr_known_value() -> None:
    # sr=0.1 per-period, n=252, normal: z = 0.1*sqrt(251)/sqrt(1+0.5*0.01) ~ 1.580
    psr = probabilistic_sharpe_ratio(0.1, 252)
    assert psr == pytest.approx(0.9429, abs=2e-3)


def test_psr_at_zero_sharpe_is_half() -> None:
    assert probabilistic_sharpe_ratio(0.0, 252) == pytest.approx(0.5, abs=1e-9)


def test_psr_rejects_short_track() -> None:
    with pytest.raises(ValueError, match="n_obs"):
        probabilistic_sharpe_ratio(0.1, 1)


def test_psr_degenerate_shape_returns_half() -> None:
    # A large negative skew with high sharpe can drive the variance term <= 0.
    assert probabilistic_sharpe_ratio(2.0, 100, skew=5.0) == 0.5


def test_expected_max_sharpe_grows_with_trials() -> None:
    one = expected_max_sharpe(1, 0.1)
    few = expected_max_sharpe(10, 0.1)
    many = expected_max_sharpe(100, 0.1)
    assert one == 0.0
    assert few > 0.0
    assert many > few


def test_expected_max_sharpe_known_value() -> None:
    # N=10, std=0.1 -> ~0.1575 (see Bailey & López de Prado).
    assert expected_max_sharpe(10, 0.1) == pytest.approx(0.1575, abs=5e-3)


def test_expected_max_sharpe_zero_dispersion() -> None:
    assert expected_max_sharpe(50, 0.0) == 0.0


def test_deflated_sharpe_below_psr_under_multiple_testing() -> None:
    # Deflating against the expected max of many trials lowers the probability.
    psr = probabilistic_sharpe_ratio(0.15, 252)
    dsr = deflated_sharpe_ratio(0.15, 252, n_trials=100, trials_sharpe_std=0.1)
    assert dsr < psr
    assert 0.0 <= dsr <= 1.0


def test_deflated_sharpe_strong_survives() -> None:
    # A genuinely strong Sharpe over a long track still clears deflation.
    dsr = deflated_sharpe_ratio(0.25, 2520, n_trials=31, trials_sharpe_std=0.08)
    assert dsr > 0.9


def test_invalid_trials() -> None:
    with pytest.raises(ValueError):
        expected_max_sharpe(0, 0.1)
    with pytest.raises(ValueError):
        expected_max_sharpe(10, -1.0)
    assert math.isfinite(expected_max_sharpe(2, 0.1))
