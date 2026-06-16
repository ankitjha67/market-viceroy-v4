"""Integration test for dual_momentum_gem."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.strategies.trend.dual_momentum_gem.strategy import DualMomentumGEM


def _panel(seed: int = 42, years: float = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    configs = {
        "SPY": (0.0006, 0.011),
        "VEU": (0.0004, 0.012),
        "AGG": (0.00015, 0.003),
        "SHY": (0.00005, 0.001),
    }
    prices: dict[str, np.ndarray] = {}
    for sym, (drift, vol) in configs.items():
        shocks = rng.normal(drift, vol, size=n)
        prices[sym] = 100.0 * np.exp(np.cumsum(shocks))
    return pd.DataFrame(prices, index=idx)


@pytest.mark.integration
def test_dual_momentum_gem_backtest_runs() -> None:
    prices = _panel()
    result = vectorbt_bridge.run(
        strategy=DualMomentumGEM(),
        prices=prices,
        initial_cash=100_000.0,
    )
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "dual_momentum_gem"
    for key in ("sharpe", "sortino", "calmar", "max_drawdown"):
        assert np.isfinite(result.metrics[key])
    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_dual_momentum_gem_backtest_deterministic() -> None:
    prices = _panel(seed=1)
    a = vectorbt_bridge.run(strategy=DualMomentumGEM(), prices=prices)
    b = vectorbt_bridge.run(strategy=DualMomentumGEM(), prices=prices)
    pd.testing.assert_frame_equal(a.weights, b.weights)
