"""Integration test for xs_momentum_jt through the vectorbt bridge."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.strategies.trend.xs_momentum_jt.strategy import CrossSectionalMomentumJT


def _panel(seed: int = 42, years: float = 4, n_symbols: int = 10) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n_days, freq="B")
    prices: dict[str, np.ndarray] = {}
    for i in range(n_symbols):
        drift = 0.0008 - 0.00015 * i  # S0 strongest, S9 weakest
        shocks = rng.normal(drift, 0.012, size=n_days)
        prices[f"S{i}"] = 100.0 * np.exp(np.cumsum(shocks))
    return pd.DataFrame(prices, index=idx)


@pytest.mark.integration
def test_xs_momentum_jt_backtest_runs() -> None:
    prices = _panel()
    result = vectorbt_bridge.run(
        strategy=CrossSectionalMomentumJT(),
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
    )
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "xs_momentum_jt"
    assert result.meta["paper_doi"] == "10.1111/j.1540-6261.1993.tb04702.x"
    for key in ("sharpe", "sortino", "calmar", "max_drawdown"):
        assert np.isfinite(result.metrics[key])
    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_xs_momentum_jt_backtest_deterministic() -> None:
    prices = _panel(seed=1)
    a = vectorbt_bridge.run(strategy=CrossSectionalMomentumJT(), prices=prices)
    b = vectorbt_bridge.run(strategy=CrossSectionalMomentumJT(), prices=prices)
    pd.testing.assert_frame_equal(a.weights, b.weights)
