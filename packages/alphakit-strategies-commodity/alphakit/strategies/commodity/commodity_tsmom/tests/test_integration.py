"""Integration tests for commodity_tsmom.

Mocks ``YFinanceFuturesAdapter.fetch`` to return a deterministic
synthetic multi-commodity panel, runs the strategy through the
vectorbt bridge, and asserts the returned :class:`BacktestResult`
is internally consistent.

Network is never touched; yfinance-futures is mocked at the adapter-
method level.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.futures.yfinance_futures_adapter import YFinanceFuturesAdapter
from alphakit.strategies.commodity.commodity_tsmom.strategy import CommodityTSMOM12m1m


def _synthetic_commodity_panel(seed: int = 42, years: float = 5) -> pd.DataFrame:
    """A deterministic 8-commodity panel with realistic drift and vol.

    Includes strong trends (CL=F, GC=F), mild trends (NG=F, SI=F, HG=F),
    and noisy/range-bound (ZC=F, ZS=F, ZW=F) so the vol-targeter has
    something to scale across the panel.
    """
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    configs = {
        "CL=F": (0.0006, 0.020),
        "NG=F": (0.0001, 0.030),
        "GC=F": (0.0004, 0.012),
        "SI=F": (0.0003, 0.020),
        "HG=F": (0.0003, 0.018),
        "ZC=F": (0.0001, 0.014),
        "ZS=F": (0.0002, 0.013),
        "ZW=F": (0.0001, 0.016),
    }

    prices: dict[str, np.ndarray] = {}
    for symbol, (drift, vol) in configs.items():
        shocks = rng.normal(drift, vol, size=n_days)
        prices[symbol] = 100.0 * np.exp(np.cumsum(shocks))
    return pd.DataFrame(prices, index=index)


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_yfinance_futures() -> None:
    panel = _synthetic_commodity_panel(seed=42, years=5)

    with patch.object(YFinanceFuturesAdapter, "fetch", return_value=panel) as mock_fetch:
        adapter = YFinanceFuturesAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
        assert mock_fetch.called

    strategy = CommodityTSMOM12m1m()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "commodity_tsmom"
    assert result.meta["paper_doi"] == "10.1111/jofi.12021"

    assert len(result.equity_curve) == len(prices)
    assert len(result.returns) == len(prices)
    assert result.weights.shape == prices.shape

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics, f"missing metric: {key}"
        assert np.isfinite(result.metrics[key]), f"non-finite metric: {key}"

    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_yfinance_futures() -> None:
    panel = _synthetic_commodity_panel(seed=123, years=4)

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

    strategy = CommodityTSMOM12m1m()
    result_a = vectorbt_bridge.run(strategy=strategy, prices=prices_a)
    result_b = vectorbt_bridge.run(strategy=strategy, prices=prices_b)

    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    pd.testing.assert_frame_equal(result_a.weights, result_b.weights)
    for key, value in result_a.metrics.items():
        assert result_b.metrics[key] == pytest.approx(value)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["CL=F", "GC=F"],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=CommodityTSMOM12m1m(), prices=empty)
