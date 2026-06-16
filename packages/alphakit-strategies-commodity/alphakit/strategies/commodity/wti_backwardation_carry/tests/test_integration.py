"""Integration tests for wti_backwardation_carry.

Mocks ``YFinanceFuturesAdapter.fetch`` to return a deterministic
synthetic 2-column WTI panel (CL=F front + CL2=F next), runs the
strategy through the vectorbt bridge, and asserts the returned
:class:`BacktestResult` is internally consistent.

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
from alphakit.strategies.commodity.wti_backwardation_carry.strategy import (
    WTIBackwardationCarry,
)


def _synthetic_wti_curve(seed: int = 42, years: float = 5) -> pd.DataFrame:
    """Deterministic 2-column WTI panel with regime alternation.

    The curve is in backwardation for ~60% of the sample (driven by
    a positive front-vs-next premium with a slow-mean-reverting
    process) and in contango for the rest. The vol on the front is
    higher than on the next, mimicking the typical commodity-curve
    term structure.
    """
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    # Slow-moving "premium" process — Ornstein-Uhlenbeck-ish
    premium = np.zeros(n_days)
    premium[0] = 0.0
    for i in range(1, n_days):
        premium[i] = 0.95 * premium[i - 1] + rng.normal(0.001, 0.002)

    front_log = np.cumsum(rng.normal(0.0003, 0.020, size=n_days))
    nxt_log = np.cumsum(rng.normal(0.0003, 0.018, size=n_days))

    front = 80.0 * np.exp(front_log) * (1.0 + premium)
    nxt = 80.0 * np.exp(nxt_log)

    return pd.DataFrame({"CL=F": front, "CL2=F": nxt}, index=index)


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_yfinance_futures() -> None:
    panel = _synthetic_wti_curve(seed=42, years=5)

    with patch.object(YFinanceFuturesAdapter, "fetch", return_value=panel) as mock_fetch:
        adapter = YFinanceFuturesAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
        assert mock_fetch.called

    strategy = WTIBackwardationCarry()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "wti_backwardation_carry"
    assert result.meta["paper_doi"] == "10.2469/faj.v62.n2.4084"

    assert len(result.equity_curve) == len(prices)
    assert len(result.returns) == len(prices)
    # Bridge reindex_like expands single-column strategy output to all
    # input columns, zero-filling the untraded leg. Verify shape and
    # that the next-month leg is all zeros.
    assert result.weights.shape == prices.shape
    assert (result.weights["CL2=F"] == 0.0).all(), "next-month leg must be untraded"

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics, f"missing metric: {key}"
        assert np.isfinite(result.metrics[key]), f"non-finite metric: {key}"

    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_yfinance_futures() -> None:
    panel = _synthetic_wti_curve(seed=123, years=4)

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

    strategy = WTIBackwardationCarry()
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
        columns=["CL=F", "CL2=F"],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=WTIBackwardationCarry(), prices=empty)
