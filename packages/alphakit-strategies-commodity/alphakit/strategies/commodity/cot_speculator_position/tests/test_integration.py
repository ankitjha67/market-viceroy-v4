"""Integration tests for cot_speculator_position.

Mocks ``YFinanceFuturesAdapter.fetch`` to return a deterministic
synthetic 8-column panel (4 prices + 4 net-speculator-position
series), runs the strategy through the vectorbt bridge, and
asserts the returned :class:`BacktestResult` is internally
consistent.
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
from alphakit.strategies.commodity.cot_speculator_position.strategy import (
    COTSpeculatorPosition,
)


def _synthetic_panel(seed: int = 42, years: float = 5) -> pd.DataFrame:
    """Deterministic 8-column panel: 4 prices + 4 positioning series.

    Positioning series are synthetic AR(1) processes that exhibit
    realistic mean reversion and tail extremes — substitute for
    real CFTC COT data in fixture tests. Prices follow standard
    log-normal walks with commodity-specific drift / vol.
    """
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    price_configs = {
        "CL=F": (0.0006, 0.020),
        "NG=F": (0.0001, 0.030),
        "GC=F": (0.0004, 0.012),
        "ZC=F": (0.0001, 0.014),
    }

    data: dict[str, np.ndarray] = {}
    for symbol, (drift, vol) in price_configs.items():
        shocks = rng.normal(drift, vol, size=n_days)
        data[symbol] = 100.0 * np.exp(np.cumsum(shocks))

        # AR(1) positioning around 0.5 in the long-fraction convention
        # (NC_long / OI). Bounded in (0, 1) so the bridge can validate
        # it as a tradeable price input.
        pos = np.full(n_days, 0.5)
        for i in range(1, n_days):
            pos[i] = 0.95 * (pos[i - 1] - 0.5) + 0.5 + rng.normal(0, 0.02)
        data[f"{symbol}_NET_SPEC"] = np.clip(pos, 0.05, 0.95)

    return pd.DataFrame(data, index=index)


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_yfinance_futures() -> None:
    panel = _synthetic_panel(seed=42, years=5)

    with patch.object(YFinanceFuturesAdapter, "fetch", return_value=panel) as mock_fetch:
        adapter = YFinanceFuturesAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
        assert mock_fetch.called

    strategy = COTSpeculatorPosition()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "cot_speculator_position"
    assert result.meta["paper_doi"] == "10.1111/0022-1082.00253"

    assert len(result.equity_curve) == len(prices)
    assert len(result.returns) == len(prices)
    # Bridge reindex_like expands strategy output (4 fronts) to all 8
    # input columns, zero-filling the untraded positioning columns.
    assert result.weights.shape == prices.shape
    for col in strategy.position_columns:
        assert (result.weights[col] == 0.0).all(), f"positioning leg {col} must be untraded"

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics, f"missing metric: {key}"
        assert np.isfinite(result.metrics[key]), f"non-finite metric: {key}"

    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_yfinance_futures() -> None:
    panel = _synthetic_panel(seed=123, years=4)

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

    strategy = COTSpeculatorPosition()
    result_a = vectorbt_bridge.run(strategy=strategy, prices=prices_a)
    result_b = vectorbt_bridge.run(strategy=strategy, prices=prices_b)

    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    pd.testing.assert_frame_equal(result_a.weights, result_b.weights)
    for key, value in result_a.metrics.items():
        assert result_b.metrics[key] == pytest.approx(value)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    s = COTSpeculatorPosition()
    cols = s.front_symbols + s.position_columns
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=cols, dtype=float)
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=s, prices=empty)
