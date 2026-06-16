"""Integration test for sma_cross_10_30."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.strategies.trend.sma_cross_10_30.strategy import SMACross1030


def _panel(seed: int = 42, years: float = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    cfgs = {"SPY": (0.0006, 0.010), "EFA": (0.0002, 0.011), "AGG": (0.00005, 0.003)}
    prices = {
        sym: 100.0 * np.exp(np.cumsum(rng.normal(drift, vol, size=n)))
        for sym, (drift, vol) in cfgs.items()
    }
    return pd.DataFrame(prices, index=idx)


@pytest.mark.integration
def test_sma_cross_10_30_backtest_runs() -> None:
    prices = _panel()
    result = vectorbt_bridge.run(strategy=SMACross1030(), prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "sma_cross_10_30"
    for key in ("sharpe", "sortino", "calmar", "max_drawdown"):
        assert np.isfinite(result.metrics[key])
    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_sma_cross_10_30_deterministic() -> None:
    prices = _panel(seed=1)
    a = vectorbt_bridge.run(strategy=SMACross1030(), prices=prices)
    b = vectorbt_bridge.run(strategy=SMACross1030(), prices=prices)
    pd.testing.assert_frame_equal(a.weights, b.weights)
