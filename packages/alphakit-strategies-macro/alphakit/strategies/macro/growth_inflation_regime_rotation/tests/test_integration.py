"""Integration tests for growth_inflation_regime_rotation.

Mocks ``YFinanceAdapter.fetch`` for the 4 tradable ETFs; the two
FRED informational columns are constructed inline. Runs the
strategy through the vectorbt bridge and asserts the returned
:class:`BacktestResult` is internally consistent, including the
two-informational-column zero-weight invariant.

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
from alphakit.strategies.macro.growth_inflation_regime_rotation.strategy import (
    GrowthInflationRegimeRotation,
)


def _synthetic_panel(seed: int = 42, years: float = 6) -> pd.DataFrame:
    """6-column panel: 4 tradable ETFs + 2 informational FRED columns.

    GDP alternates between high (3%) and low (1%) growth in 18-month
    blocks; CPI grows at ~2.5% YoY with some drift so the inflation
    dimension flips too — exercising all 4 regime cells.
    """
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    spy = 100.0 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, size=n_days)))
    tlt = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.010, size=n_days)))
    gld = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.010, size=n_days)))
    dbc = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.014, size=n_days)))

    # CPI index with time-varying inflation: 2% for first half, 4% for
    # second half (exercises the inflation-dimension flip).
    half = n_days // 2
    cpi_daily_low = (1.0 + 0.02) ** (1.0 / 252.0) - 1.0
    cpi_daily_high = (1.0 + 0.045) ** (1.0 / 252.0) - 1.0
    cpi_growth = np.concatenate(
        [np.full(half, cpi_daily_low), np.full(n_days - half, cpi_daily_high)]
    )
    cpi = 250.0 * np.exp(np.cumsum(np.log1p(cpi_growth)))

    # GDP alternating high/low in ~18-month blocks.
    block = round(1.5 * 252)
    gdp = np.empty(n_days, dtype=float)
    for i in range(0, n_days, block):
        gdp[i : i + block] = 3.0 if (i // block) % 2 == 0 else 1.0

    return pd.DataFrame(
        {
            "SPY": spy,
            "TLT": tlt,
            "GLD": gld,
            "DBC": dbc,
            "CPIAUCSL": cpi,
            "GDPC1": gdp,
        },
        index=index,
    )


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_yfinance() -> None:
    panel = _synthetic_panel(seed=42, years=6)

    with patch.object(YFinanceAdapter, "fetch", return_value=panel) as mock_fetch:
        adapter = YFinanceAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2024, 1, 1),
        )
        assert mock_fetch.called

    strategy = GrowthInflationRegimeRotation()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "growth_inflation_regime_rotation"
    assert result.meta["paper_doi"] == "10.3905/jpm.2014.40.3.087"

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics
        assert np.isfinite(result.metrics[key])

    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_both_informational_columns_zero_through_bridge() -> None:
    panel = _synthetic_panel(seed=7, years=5)

    with patch.object(YFinanceAdapter, "fetch", return_value=panel):
        adapter = YFinanceAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )

    strategy = GrowthInflationRegimeRotation()
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)

    assert (result.weights["CPIAUCSL"] == 0.0).all()
    assert (result.weights["GDPC1"] == 0.0).all()


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_yfinance() -> None:
    panel = _synthetic_panel(seed=123, years=5)

    with patch.object(YFinanceAdapter, "fetch", return_value=panel):
        adapter = YFinanceAdapter()
        prices_a = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
        prices_b = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
    pd.testing.assert_frame_equal(prices_a, prices_b)

    strategy = GrowthInflationRegimeRotation()
    result_a = vectorbt_bridge.run(strategy=strategy, prices=prices_a)
    result_b = vectorbt_bridge.run(strategy=strategy, prices=prices_b)
    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    pd.testing.assert_frame_equal(result_a.weights, result_b.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    cols = ["SPY", "TLT", "GLD", "DBC", "CPIAUCSL", "GDPC1"]
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=cols, dtype=float)
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=GrowthInflationRegimeRotation(), prices=empty)
