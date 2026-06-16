"""Integration tests for metals_momentum.

Mocks ``YFinanceFuturesAdapter.fetch`` to return a deterministic
synthetic 4-metal panel, runs the strategy through the vectorbt
bridge, and asserts the returned :class:`BacktestResult` is
internally consistent.

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
from alphakit.strategies.commodity.metals_momentum.strategy import MetalsMomentum


def _synthetic_metals_panel(seed: int = 42, years: float = 5) -> pd.DataFrame:
    """A deterministic 4-metal panel with realistic drift and vol.

    Gold and platinum are configured as mild monetary uptrends;
    silver as a higher-vol monetary leg; copper as an industrial
    leg with mild drift and elevated noise. This produces a panel
    where the vol-targeter has meaningful per-asset dispersion to
    scale across.
    """
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    configs = {
        "GC=F": (0.0004, 0.012),
        "SI=F": (0.0003, 0.020),
        "HG=F": (0.0002, 0.018),
        "PL=F": (0.0003, 0.016),
    }

    prices: dict[str, np.ndarray] = {}
    for symbol, (drift, vol) in configs.items():
        shocks = rng.normal(drift, vol, size=n_days)
        prices[symbol] = 100.0 * np.exp(np.cumsum(shocks))
    return pd.DataFrame(prices, index=index)


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_yfinance_futures() -> None:
    panel = _synthetic_metals_panel(seed=42, years=5)

    with patch.object(YFinanceFuturesAdapter, "fetch", return_value=panel) as mock_fetch:
        adapter = YFinanceFuturesAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
        assert mock_fetch.called

    strategy = MetalsMomentum()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "metals_momentum"
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
    panel = _synthetic_metals_panel(seed=123, years=4)

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

    strategy = MetalsMomentum()
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
        columns=["GC=F", "SI=F"],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=MetalsMomentum(), prices=empty)
