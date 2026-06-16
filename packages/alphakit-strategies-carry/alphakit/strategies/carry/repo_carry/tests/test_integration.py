"""Integration test for repo_carry."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.strategies.carry.repo_carry.strategy import RepoCarry


def _panel(seed: int = 42, years: float = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    cfgs = {"US10Y": (0.0002, 0.005), "US2Y": (0.0001, 0.003), "DE10Y": (0.00015, 0.004)}
    return pd.DataFrame(
        {sym: 100.0 * np.exp(np.cumsum(rng.normal(d, v, size=n))) for sym, (d, v) in cfgs.items()},
        index=idx,
    )


@pytest.mark.integration
def test_repo_carry_runs() -> None:
    prices = _panel()
    result = vectorbt_bridge.run(strategy=RepoCarry(), prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "repo_carry"
    for key in ("sharpe", "sortino", "calmar", "max_drawdown"):
        assert np.isfinite(result.metrics[key])


@pytest.mark.integration
def test_repo_carry_deterministic() -> None:
    prices = _panel(seed=1)
    a = vectorbt_bridge.run(strategy=RepoCarry(), prices=prices)
    b = vectorbt_bridge.run(strategy=RepoCarry(), prices=prices)
    pd.testing.assert_frame_equal(a.weights, b.weights)
