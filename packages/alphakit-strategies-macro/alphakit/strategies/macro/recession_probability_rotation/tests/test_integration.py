"""Integration tests for recession_probability_rotation.

Mocks both ``YFinanceAdapter.fetch`` (for the 3 tradable ETFs) and
the FRED informational column (constructed inline). Runs the
strategy through the vectorbt bridge and asserts the returned
:class:`BacktestResult` is internally consistent.

The integration test specifically verifies that the bridge
correctly handles the informational column (RECPROUSM156N at
weight 0.0 produces no orders / no drift correction).

Network is never touched; yfinance is mocked at the adapter-
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
from alphakit.data.equities.yfinance_adapter import YFinanceAdapter
from alphakit.strategies.macro.recession_probability_rotation.strategy import (
    RecessionProbabilityRotation,
)


def _synthetic_panel(seed: int = 42, years: float = 5) -> pd.DataFrame:
    """Deterministic 4-column panel: 3 tradable ETFs + FRED RECPROUSM156N."""
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    spy = 100.0 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, size=n_days)))
    tlt = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.010, size=n_days)))
    gld = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.010, size=n_days)))

    # Recession probability: low for most of the sample, with two
    # high-probability episodes (months 18-24 and months 48-54) to
    # exercise the regime-flip behaviour.
    probs = np.full(n_days, 0.10, dtype=float)
    n_per_month = n_days // (round(years * 12))
    for me_start, me_end in [(18, 24), (48, 54)]:
        start_idx = me_start * n_per_month
        end_idx = min(me_end * n_per_month, n_days)
        probs[start_idx:end_idx] = 0.55

    return pd.DataFrame(
        {
            "SPY": spy,
            "TLT": tlt,
            "GLD": gld,
            "RECPROUSM156N": probs,
        },
        index=index,
    )


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_yfinance() -> None:
    panel = _synthetic_panel(seed=42, years=5)

    with patch.object(YFinanceAdapter, "fetch", return_value=panel) as mock_fetch:
        adapter = YFinanceAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
        assert mock_fetch.called

    strategy = RecessionProbabilityRotation()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "recession_probability_rotation"
    assert result.meta["paper_doi"] == "10.1162/003465398557320"

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics
        assert np.isfinite(result.metrics[key])

    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_informational_column_is_zero_through_bridge() -> None:
    """End-to-end: the bridge must preserve the informational-column
    invariant. RECPROUSM156N weight = 0.0 through the entire weights
    DataFrame returned by vectorbt_bridge.run.
    """
    panel = _synthetic_panel(seed=7, years=3)

    with patch.object(YFinanceAdapter, "fetch", return_value=panel):
        adapter = YFinanceAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2021, 1, 1),
        )

    strategy = RecessionProbabilityRotation()
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)

    # The informational column on the bridge-side weights frame must
    # be exactly 0.0 everywhere.
    assert (result.weights["RECPROUSM156N"] == 0.0).all()


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_yfinance() -> None:
    panel = _synthetic_panel(seed=123, years=4)

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

    strategy = RecessionProbabilityRotation()
    result_a = vectorbt_bridge.run(strategy=strategy, prices=prices_a)
    result_b = vectorbt_bridge.run(strategy=strategy, prices=prices_b)
    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    pd.testing.assert_frame_equal(result_a.weights, result_b.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["SPY", "TLT", "GLD", "RECPROUSM156N"],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=RecessionProbabilityRotation(), prices=empty)
