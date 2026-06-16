"""Integration tests for grain_seasonality."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.futures.yfinance_futures_adapter import YFinanceFuturesAdapter
from alphakit.strategies.commodity.grain_seasonality.strategy import GrainSeasonality


def _synthetic_grain_panel(seed: int = 42, years: float = 5) -> pd.DataFrame:
    """Deterministic 3-grain panel with explicit seasonal signal embedded.

    The price series include an additive seasonal component so the
    integration test produces non-trivial returns when the seasonal
    long/short signal is correctly aligned.
    """
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")
    months = index.month.to_numpy()

    # Each grain has a small cosine seasonal component aligned with
    # the Sørensen calendar (peak-month logic).
    seasonal = {
        "ZC=F": np.cos(2 * np.pi * (months - 5) / 12),  # peaks May
        "ZS=F": np.cos(2 * np.pi * (months - 6) / 12),  # peaks Jun
        "ZW=F": np.cos(2 * np.pi * (months - 3) / 12),  # peaks Mar
    }

    prices: dict[str, np.ndarray] = {}
    for sym, drift in [("ZC=F", 0.0001), ("ZS=F", 0.0002), ("ZW=F", 0.0001)]:
        shocks = rng.normal(drift, 0.014, size=n_days)
        path = np.cumsum(shocks) + 0.05 * seasonal[sym]
        prices[sym] = 5.0 * np.exp(path)
    return pd.DataFrame(prices, index=index)


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_yfinance_futures() -> None:
    panel = _synthetic_grain_panel(seed=42, years=5)

    with patch.object(YFinanceFuturesAdapter, "fetch", return_value=panel) as mock_fetch:
        adapter = YFinanceFuturesAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
        assert mock_fetch.called

    strategy = GrainSeasonality()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "grain_seasonality"
    assert result.meta["paper_doi"] == "10.1002/fut.10017"

    assert len(result.equity_curve) == len(prices)
    assert len(result.returns) == len(prices)
    assert result.weights.shape == prices.shape

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics, f"missing metric: {key}"
        assert np.isfinite(result.metrics[key]), f"non-finite metric: {key}"

    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_yfinance_futures() -> None:
    panel = _synthetic_grain_panel(seed=123, years=4)

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

    strategy = GrainSeasonality()
    result_a = vectorbt_bridge.run(strategy=strategy, prices=prices_a)
    result_b = vectorbt_bridge.run(strategy=strategy, prices=prices_b)

    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    pd.testing.assert_frame_equal(result_a.weights, result_b.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    s = GrainSeasonality()
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=s.front_symbols,
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=s, prices=empty)
