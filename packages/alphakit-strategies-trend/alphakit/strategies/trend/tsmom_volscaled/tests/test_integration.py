"""Integration test for tsmom_volscaled through the vectorbt bridge."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.strategies.trend.tsmom_volscaled.strategy import TimeSeriesMomentumVolScaled


def _synthetic_panel(seed: int = 42, years: float = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")
    configs = {
        "SPY": (0.0006, 0.010),
        "EFA": (0.0002, 0.011),
        "EEM": (0.0003, 0.014),
        "AGG": (0.00005, 0.003),
        "GLD": (0.0004, 0.009),
        "DBC": (0.0002, 0.013),
    }
    prices: dict[str, np.ndarray] = {}
    for symbol, (drift, vol) in configs.items():
        shocks = rng.normal(drift, vol, size=n_days)
        prices[symbol] = 100.0 * np.exp(np.cumsum(shocks))
    return pd.DataFrame(prices, index=index)


@pytest.mark.integration
def test_tsmom_volscaled_backtest_runs() -> None:
    prices = _synthetic_panel(seed=42)
    result = vectorbt_bridge.run(
        strategy=TimeSeriesMomentumVolScaled(),
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
    )
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "tsmom_volscaled"
    assert result.meta["paper_doi"] == "10.2139/ssrn.2993026"
    assert len(result.equity_curve) == len(prices)
    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics
        assert np.isfinite(result.metrics[key])
    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_tsmom_volscaled_backtest_deterministic() -> None:
    prices = _synthetic_panel(seed=123)
    a = vectorbt_bridge.run(strategy=TimeSeriesMomentumVolScaled(), prices=prices)
    b = vectorbt_bridge.run(strategy=TimeSeriesMomentumVolScaled(), prices=prices)
    pd.testing.assert_series_equal(a.equity_curve, b.equity_curve)
    pd.testing.assert_frame_equal(a.weights, b.weights)
