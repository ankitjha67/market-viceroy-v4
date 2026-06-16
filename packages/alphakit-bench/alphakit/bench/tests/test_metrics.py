"""Tests for alphakit.bench.metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd
from alphakit.bench.metrics import (
    capacity_estimate_bn,
    regime_performance,
    turnover_annual,
)


def _random_weights(seed: int = 42, days: int = 500, assets: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=days, freq="B")
    w = rng.dirichlet(np.ones(assets), size=days)
    return pd.DataFrame(w, index=idx, columns=[f"A{i}" for i in range(assets)])


def _random_returns(seed: int = 42, days: int = 500) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=days, freq="B")
    return pd.Series(rng.normal(0.0003, 0.01, size=days), index=idx)


class TestTurnoverAnnual:
    def test_empty_weights(self) -> None:
        w = pd.DataFrame()
        assert turnover_annual(w) == 0.0

    def test_single_row(self) -> None:
        w = pd.DataFrame({"A": [0.5]})
        assert turnover_annual(w) == 0.0

    def test_constant_weights(self) -> None:
        idx = pd.date_range("2020-01-01", periods=100, freq="B")
        w = pd.DataFrame({"A": [0.5] * 100, "B": [0.5] * 100}, index=idx)
        assert turnover_annual(w) == 0.0

    def test_positive_turnover(self) -> None:
        w = _random_weights()
        to = turnover_annual(w)
        assert to > 0.0
        assert np.isfinite(to)


class TestCapacityEstimate:
    def test_zero_turnover(self) -> None:
        assert capacity_estimate_bn(0.0) == 0.0

    def test_positive_turnover(self) -> None:
        cap = capacity_estimate_bn(10.0)
        assert cap > 0.0
        assert np.isfinite(cap)

    def test_higher_turnover_lower_capacity(self) -> None:
        assert capacity_estimate_bn(20.0) < capacity_estimate_bn(10.0)


class TestRegimePerformance:
    def test_short_series(self) -> None:
        r = pd.Series([0.01, 0.02])
        result = regime_performance(r)
        assert result["bull_market_sharpe"] == 0.0
        assert result["bear_market_sharpe"] == 0.0
        assert result["sideways_sharpe"] == 0.0

    def test_returns_all_keys(self) -> None:
        r = _random_returns(days=500)
        result = regime_performance(r)
        assert "bull_market_sharpe" in result
        assert "bear_market_sharpe" in result
        assert "sideways_sharpe" in result

    def test_values_are_finite(self) -> None:
        r = _random_returns(days=500)
        result = regime_performance(r)
        for v in result.values():
            assert np.isfinite(v)
