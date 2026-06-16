"""Integration tests for commodity_curve_carry.

Mocks ``YFinanceFuturesAdapter.fetch`` to return a deterministic
synthetic 16-column commodity panel (8 fronts + 8 next-months),
runs the strategy through the vectorbt bridge, and asserts the
returned :class:`BacktestResult` is internally consistent.
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
from alphakit.strategies.commodity.commodity_curve_carry.strategy import (
    CommodityCurveCarry,
)


def _synthetic_panel(seed: int = 42, years: float = 5) -> pd.DataFrame:
    """Deterministic 16-column commodity panel: 8 fronts + 8 next-months.

    Each commodity has its own drift, vol, and curve premium. The
    cross-section spans backwardated commodities (energy, metals)
    and contangoed commodities (grains) so the rank book has
    meaningful long and short legs.
    """
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    configs = {
        "CL=F": (0.0006, 0.020, +0.04),
        "NG=F": (0.0001, 0.030, -0.06),
        "GC=F": (0.0004, 0.012, +0.01),
        "SI=F": (0.0003, 0.020, +0.02),
        "HG=F": (0.0003, 0.018, +0.03),
        "ZC=F": (0.0001, 0.014, -0.02),
        "ZS=F": (0.0002, 0.013, -0.03),
        "ZW=F": (0.0001, 0.016, -0.04),
    }

    prices: dict[str, np.ndarray] = {}
    for symbol, (drift, vol, premium) in configs.items():
        shocks = rng.normal(drift, vol, size=n_days)
        front = 100.0 * np.exp(np.cumsum(shocks))
        # Next-month is front × (1 - premium) — positive premium = backwardation
        nxt = front * (1.0 - premium + rng.normal(0, 0.005, size=n_days))
        prices[symbol] = front
        prices[f"{symbol[:-2]}2=F"] = np.maximum(nxt, 0.5)
    return pd.DataFrame(prices, index=index)


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

    strategy = CommodityCurveCarry()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "commodity_curve_carry"
    assert result.meta["paper_doi"] == "10.1016/j.jfineco.2017.11.002"

    assert len(result.equity_curve) == len(prices)
    assert len(result.returns) == len(prices)
    # Bridge reindex_like expands strategy output (8 fronts) to all 16
    # input columns, zero-filling the untraded next-month legs.
    assert result.weights.shape == prices.shape
    next_cols = [f"{f[:-2]}2=F" for f in strategy.front_symbols]
    for col in next_cols:
        assert (result.weights[col] == 0.0).all(), f"next-month leg {col} must be untraded"

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

    strategy = CommodityCurveCarry()
    result_a = vectorbt_bridge.run(strategy=strategy, prices=prices_a)
    result_b = vectorbt_bridge.run(strategy=strategy, prices=prices_b)

    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    pd.testing.assert_frame_equal(result_a.weights, result_b.weights)
    for key, value in result_a.metrics.items():
        assert result_b.metrics[key] == pytest.approx(value)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    s = CommodityCurveCarry()
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=s.front_symbols + s.next_symbols,
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=s, prices=empty)
