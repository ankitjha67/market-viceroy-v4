"""Integration tests for wti_brent_spread."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.futures.yfinance_futures_adapter import YFinanceFuturesAdapter
from alphakit.strategies.commodity.wti_brent_spread.strategy import WTIBrentSpread


def _synthetic_wti_brent_panel(seed: int = 42, years: float = 5) -> pd.DataFrame:
    """Cointegrated WTI-Brent panel with a slow-mean-reverting spread."""
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    market = np.cumsum(rng.normal(0.0001, 0.018, size=n_days))
    cl = 80.0 * np.exp(market)

    # Brent = WTI + structural premium + AR(1) deviation
    spread_state = -3.0
    spread_path = np.full(n_days, -3.0)
    for i in range(1, n_days):
        spread_state = -3.0 + 0.97 * (spread_state + 3.0) + rng.normal(0, 1.0)
        spread_path[i] = spread_state
    bz = cl - spread_path  # if spread = CL - BZ, then BZ = CL - spread

    return pd.DataFrame(
        {"CL=F": cl, "BZ=F": np.maximum(bz, 1.0)},
        index=index,
    )


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_yfinance_futures() -> None:
    panel = _synthetic_wti_brent_panel(seed=42, years=5)

    with patch.object(YFinanceFuturesAdapter, "fetch", return_value=panel) as mock_fetch:
        adapter = YFinanceFuturesAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
        assert mock_fetch.called

    strategy = WTIBrentSpread()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "wti_brent_spread"
    assert result.meta["paper_doi"] == "10.1016/j.eneco.2011.04.006"

    assert len(result.equity_curve) == len(prices)
    assert len(result.returns) == len(prices)
    assert result.weights.shape == prices.shape

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics, f"missing metric: {key}"
        assert np.isfinite(result.metrics[key]), f"non-finite metric: {key}"

    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_yfinance_futures() -> None:
    panel = _synthetic_wti_brent_panel(seed=123, years=4)

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

    strategy = WTIBrentSpread()
    result_a = vectorbt_bridge.run(strategy=strategy, prices=prices_a)
    result_b = vectorbt_bridge.run(strategy=strategy, prices=prices_b)

    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    pd.testing.assert_frame_equal(result_a.weights, result_b.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    s = WTIBrentSpread()
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=s.front_symbols, dtype=float)
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=s, prices=empty)
