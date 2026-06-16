"""Integration test for residual_momentum."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.strategies.trend.residual_momentum.strategy import ResidualMomentum


def _panel(seed: int = 42, years: float = 4, n_symbols: int = 10) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    prices: dict[str, np.ndarray] = {}
    for i in range(n_symbols):
        drift = 0.0008 - 0.00015 * i
        shocks = rng.normal(drift, 0.012, size=n)
        prices[f"S{i}"] = 100.0 * np.exp(np.cumsum(shocks))
    return pd.DataFrame(prices, index=idx)


@pytest.mark.integration
def test_residual_momentum_backtest_runs() -> None:
    prices = _panel()
    result = vectorbt_bridge.run(
        strategy=ResidualMomentum(),
        prices=prices,
        initial_cash=100_000.0,
    )
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "residual_momentum"
    for key in ("sharpe", "sortino", "calmar", "max_drawdown"):
        assert np.isfinite(result.metrics[key])


@pytest.mark.integration
def test_residual_momentum_backtest_deterministic() -> None:
    prices = _panel(seed=1)
    a = vectorbt_bridge.run(strategy=ResidualMomentum(), prices=prices)
    b = vectorbt_bridge.run(strategy=ResidualMomentum(), prices=prices)
    pd.testing.assert_frame_equal(a.weights, b.weights)
