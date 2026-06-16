"""Integration test for bond_carry_roll."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.strategies.carry.bond_carry_roll.strategy import BondCarryRoll


def _panel(seed: int = 42, years: float = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    cfgs = {"US10Y": (0.0001, 0.005), "DE10Y": (0.0002, 0.006), "JP10Y": (-0.0001, 0.004)}
    return pd.DataFrame(
        {sym: 100.0 * np.exp(np.cumsum(rng.normal(d, v, size=n))) for sym, (d, v) in cfgs.items()},
        index=idx,
    )


@pytest.mark.integration
def test_bond_carry_roll_runs() -> None:
    prices = _panel()
    result = vectorbt_bridge.run(strategy=BondCarryRoll(), prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "bond_carry_roll"
    for key in ("sharpe", "sortino", "calmar", "max_drawdown"):
        assert np.isfinite(result.metrics[key])


@pytest.mark.integration
def test_bond_carry_roll_deterministic() -> None:
    prices = _panel(seed=1)
    a = vectorbt_bridge.run(strategy=BondCarryRoll(), prices=prices)
    b = vectorbt_bridge.run(strategy=BondCarryRoll(), prices=prices)
    pd.testing.assert_frame_equal(a.weights, b.weights)
