"""Integration tests for gtaa_cross_asset_momentum.

Mocks ``YFinanceAdapter.fetch`` to return a deterministic synthetic
9-ETF panel, runs the strategy through the vectorbt bridge, and
asserts the returned :class:`BacktestResult` is internally
consistent.

Network is never touched; yfinance is mocked at the adapter-method
level.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.equities.yfinance_adapter import YFinanceAdapter
from alphakit.strategies.macro.gtaa_cross_asset_momentum.strategy import (
    GtaaCrossAssetMomentum,
)


def _synthetic_gtaa_panel(seed: int = 42, years: float = 5) -> pd.DataFrame:
    """Deterministic 9-ETF panel with realistic per-asset drift and vol."""
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    configs = {
        "SPY": (0.0004, 0.012),
        "EFA": (0.0002, 0.013),
        "EEM": (0.0001, 0.017),
        "AGG": (0.00005, 0.003),
        "TLT": (0.0001, 0.010),
        "HYG": (0.0002, 0.006),
        "GLD": (0.0003, 0.010),
        "DBC": (0.0001, 0.014),
        "VNQ": (0.0002, 0.013),
    }

    prices: dict[str, np.ndarray] = {}
    for symbol, (drift, vol) in configs.items():
        shocks = rng.normal(drift, vol, size=n_days)
        prices[symbol] = 100.0 * np.exp(np.cumsum(shocks))
    return pd.DataFrame(prices, index=index)


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_yfinance() -> None:
    panel = _synthetic_gtaa_panel(seed=42, years=5)

    with patch.object(YFinanceAdapter, "fetch", return_value=panel) as mock_fetch:
        adapter = YFinanceAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
        assert mock_fetch.called

    strategy = GtaaCrossAssetMomentum()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "gtaa_cross_asset_momentum"
    assert result.meta["paper_doi"] == "10.1111/jofi.12021"

    assert len(result.equity_curve) == len(prices)
    assert len(result.returns) == len(prices)
    assert result.weights.shape == prices.shape

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics, f"missing metric: {key}"
        assert np.isfinite(result.metrics[key]), f"non-finite metric: {key}"

    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_yfinance() -> None:
    panel = _synthetic_gtaa_panel(seed=123, years=4)

    with patch.object(YFinanceAdapter, "fetch", return_value=panel):
        adapter = YFinanceAdapter()
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

    strategy = GtaaCrossAssetMomentum()
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
        columns=["SPY", "TLT", "GLD"],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=GtaaCrossAssetMomentum(), prices=empty)
