"""Integration tests for crush_spread."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.futures.yfinance_futures_adapter import YFinanceFuturesAdapter
from alphakit.strategies.commodity.crush_spread.strategy import CrushSpread


def _synthetic_crush_panel(seed: int = 42, years: float = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    # Spread mean-reverts around a stable centre
    spread_state = 0.0
    spread_path = np.zeros(n_days)
    for i in range(1, n_days):
        spread_state = 0.97 * spread_state + rng.normal(0, 8.0)
        spread_path[i] = spread_state

    market = np.cumsum(rng.normal(0.0001, 0.014, size=n_days))
    zs = 1000.0 * np.exp(market) + spread_path
    zm = 300.0 * np.exp(market) + 0.5 * spread_path
    zl = 40.0 * np.exp(market) + 0.1 * spread_path

    return pd.DataFrame(
        {
            "ZS=F": np.maximum(zs, 100.0),
            "ZM=F": np.maximum(zm, 50.0),
            "ZL=F": np.maximum(zl, 5.0),
        },
        index=index,
    )


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_yfinance_futures() -> None:
    panel = _synthetic_crush_panel(seed=42, years=5)

    with patch.object(YFinanceFuturesAdapter, "fetch", return_value=panel) as mock_fetch:
        adapter = YFinanceFuturesAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
        assert mock_fetch.called

    strategy = CrushSpread()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "crush_spread"
    assert result.meta["paper_doi"].startswith("10.1002/(SICI)1096-9934(199905)")

    assert len(result.equity_curve) == len(prices)
    assert len(result.returns) == len(prices)
    assert result.weights.shape == prices.shape

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics, f"missing metric: {key}"
        assert np.isfinite(result.metrics[key]), f"non-finite metric: {key}"

    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_yfinance_futures() -> None:
    panel = _synthetic_crush_panel(seed=123, years=4)

    with patch.object(YFinanceFuturesAdapter, "fetch", return_value=panel):
        adapter = YFinanceFuturesAdapter()
        prices_a = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2022, 1, 1),
        )
        prices_b = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2022, 1, 1),
        )
    pd.testing.assert_frame_equal(prices_a, prices_b)

    strategy = CrushSpread()
    result_a = vectorbt_bridge.run(strategy=strategy, prices=prices_a)
    result_b = vectorbt_bridge.run(strategy=strategy, prices=prices_b)

    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    pd.testing.assert_frame_equal(result_a.weights, result_b.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    s = CrushSpread()
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=s.front_symbols, dtype=float)
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=s, prices=empty)
