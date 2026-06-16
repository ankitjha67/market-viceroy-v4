"""Integration test for fx_carry_em."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.strategies.carry.fx_carry_em.strategy import FXCarryEM


def _panel(seed: int = 42, years: float = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    cfgs = {"BRLUSD": (0.0002, 0.010), "MXNUSD": (0.0003, 0.012), "ZARUSD": (-0.0001, 0.011)}
    return pd.DataFrame(
        {sym: 100.0 * np.exp(np.cumsum(rng.normal(d, v, size=n))) for sym, (d, v) in cfgs.items()},
        index=idx,
    )


@pytest.mark.integration
def test_fx_carry_em_runs() -> None:
    prices = _panel()
    result = vectorbt_bridge.run(strategy=FXCarryEM(n_long=1, n_short=1), prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "fx_carry_em"
    for key in ("sharpe", "sortino", "calmar", "max_drawdown"):
        assert np.isfinite(result.metrics[key])


@pytest.mark.integration
def test_fx_carry_em_deterministic() -> None:
    prices = _panel(seed=1)
    a = vectorbt_bridge.run(strategy=FXCarryEM(n_long=1, n_short=1), prices=prices)
    b = vectorbt_bridge.run(strategy=FXCarryEM(n_long=1, n_short=1), prices=prices)
    pd.testing.assert_frame_equal(a.weights, b.weights)
