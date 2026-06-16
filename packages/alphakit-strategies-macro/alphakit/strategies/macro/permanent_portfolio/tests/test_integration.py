"""Integration tests for permanent_portfolio.

Mocks ``YFinanceAdapter.fetch`` to return a deterministic synthetic
4-leg panel, runs the strategy through the vectorbt bridge, and
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
from alphakit.strategies.macro.permanent_portfolio.strategy import PermanentPortfolio


def _synthetic_permanent_panel(seed: int = 42, years: float = 5) -> pd.DataFrame:
    """A deterministic 4-leg panel mimicking SPY / TLT / GLD / SHY return
    characteristics: SPY has equity-like vol and drift; TLT has bond-like
    duration; GLD has commodity-like vol with weak drift; SHY has near-cash
    vol with mild drift.
    """
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    configs = {
        "SPY": (0.0004, 0.012),  # ~10% annual drift, 19% annual vol
        "TLT": (0.0001, 0.008),  # ~2.5% annual drift, 13% annual vol
        "GLD": (0.0002, 0.009),  # ~5% annual drift, 14% annual vol
        "SHY": (0.00005, 0.0005),  # ~1.25% annual drift, 0.8% annual vol
    }

    prices: dict[str, np.ndarray] = {}
    for symbol, (drift, vol) in configs.items():
        shocks = rng.normal(drift, vol, size=n_days)
        prices[symbol] = 100.0 * np.exp(np.cumsum(shocks))
    return pd.DataFrame(prices, index=index)


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_yfinance() -> None:
    panel = _synthetic_permanent_panel(seed=42, years=5)

    with patch.object(YFinanceAdapter, "fetch", return_value=panel) as mock_fetch:
        adapter = YFinanceAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
        assert mock_fetch.called

    strategy = PermanentPortfolio()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "permanent_portfolio"
    assert result.meta["paper_doi"] == "10.2139/ssrn.3168697"

    assert len(result.equity_curve) == len(prices)
    assert len(result.returns) == len(prices)
    assert result.weights.shape == prices.shape

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics, f"missing metric: {key}"
        assert np.isfinite(result.metrics[key]), f"non-finite metric: {key}"

    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_weights_are_static_25_25_25_25_at_each_rebalance() -> None:
    """End-to-end: the bridge receives 0.25 on each leg at every month-end.

    This is the integration-side mirror of the unit-test assertion; verifies
    that the bridge's weight-pipeline preserves the constant 25/25/25/25
    target between strategy.generate_signals() and result.weights.
    """
    panel = _synthetic_permanent_panel(seed=7, years=3)

    with patch.object(YFinanceAdapter, "fetch", return_value=panel):
        adapter = YFinanceAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2021, 1, 1),
        )

    strategy = PermanentPortfolio()
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)

    # Find month-end bars on the result's weights index.
    idx = result.weights.index
    assert isinstance(idx, pd.DatetimeIndex)
    month_end_mask = idx.to_series().groupby(idx.to_period("M")).transform("max") == idx.to_series()
    month_end_weights = result.weights.loc[month_end_mask]
    # From the first month-end onward, every month-end row equals 0.25 across
    # the four legs (warm-up rows before the first month-end are zero).
    first_month_end = pd.Timestamp("2018-01-31")
    mature = month_end_weights.loc[month_end_weights.index >= first_month_end]
    np.testing.assert_allclose(mature.to_numpy(), 0.25, atol=1e-12)


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_yfinance() -> None:
    panel = _synthetic_permanent_panel(seed=123, years=4)

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

    strategy = PermanentPortfolio()
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
        columns=["SPY", "TLT", "GLD", "SHY"],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=PermanentPortfolio(), prices=empty)
