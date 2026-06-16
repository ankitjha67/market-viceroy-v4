"""Integration tests for inflation_regime_allocation.

Mocks ``YFinanceAdapter.fetch`` for the 4 tradable ETFs; the
CPIAUCSL informational column is constructed inline and cycles
through low / moderate / high inflation regimes. Runs the strategy
through the vectorbt bridge and asserts the returned
:class:`BacktestResult` is internally consistent, including the
informational-column zero-weight invariant.

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
from alphakit.strategies.macro.inflation_regime_allocation.strategy import (
    InflationRegimeAllocation,
)


def _synthetic_panel(seed: int = 42, years: float = 6) -> pd.DataFrame:
    """5-column panel: 4 tradable ETFs + 1 CPIAUCSL informational column.

    CPIAUCSL cycles through three inflation regimes (low/moderate/high)
    in ~2-year blocks, exercising all 3 cells. All values strictly positive.
    """
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    spy = 100.0 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, size=n_days)))
    tlt = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.010, size=n_days)))
    gld = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.010, size=n_days)))
    dbc = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.014, size=n_days)))

    # CPI index: 2-year blocks of low (1%), moderate (3%), high (6%) growth.
    block = round(2.0 * 252)
    cpi_daily_rates = {
        0: (1.0 + 0.01) ** (1.0 / 252.0) - 1.0,  # 1% YoY → low
        1: (1.0 + 0.03) ** (1.0 / 252.0) - 1.0,  # 3% YoY → moderate
        2: (1.0 + 0.06) ** (1.0 / 252.0) - 1.0,  # 6% YoY → high
    }
    cpi_growth = np.empty(n_days, dtype=float)
    for i in range(0, n_days, block):
        end = min(i + block, n_days)
        block_idx = (i // block) % 3
        cpi_growth[i:end] = cpi_daily_rates[block_idx]

    cpi = 250.0 * np.exp(np.cumsum(np.log1p(cpi_growth)))

    return pd.DataFrame(
        {
            "SPY": spy,
            "TLT": tlt,
            "GLD": gld,
            "DBC": dbc,
            "CPIAUCSL": cpi,
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

    strategy = InflationRegimeAllocation()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "inflation_regime_allocation"
    assert result.meta["paper_doi"] == "10.2469/faj.v62.n2.4080"

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics
        assert np.isfinite(result.metrics[key])

    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_cpiaucsl_column_zero_through_bridge() -> None:
    """CPIAUCSL must carry exactly 0.0 weight in the backtest output."""
    panel = _synthetic_panel(seed=7, years=5)

    with patch.object(YFinanceAdapter, "fetch", return_value=panel):
        adapter = YFinanceAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )

    strategy = InflationRegimeAllocation()
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)

    assert (result.weights["CPIAUCSL"] == 0.0).all()


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_yfinance() -> None:
    """Two runs with identical panel produce identical equity curves and weights."""
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

    strategy = InflationRegimeAllocation()
    result_a = vectorbt_bridge.run(strategy=strategy, prices=prices_a)
    result_b = vectorbt_bridge.run(strategy=strategy, prices=prices_b)
    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    pd.testing.assert_frame_equal(result_a.weights, result_b.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    """Passing an empty DataFrame raises ValueError with 'empty' in the message."""
    cols = ["SPY", "TLT", "GLD", "DBC", "CPIAUCSL"]
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=cols, dtype=float)
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=InflationRegimeAllocation(), prices=empty)


@pytest.mark.integration
def test_all_three_regimes_exercised_in_backtest() -> None:
    """The synthetic panel exercises all 3 inflation regimes."""
    panel = _synthetic_panel(seed=42, years=6)

    strategy = InflationRegimeAllocation()
    weights = strategy.generate_signals(panel)

    # Low: SPY=0.60. Moderate: SPY=0.40. High: SPY=0.05.
    nonzero = weights[["SPY", "TLT", "GLD", "DBC"]].sum(axis=1) > 0
    assert (weights.loc[nonzero, "SPY"] == 0.60).any(), "Low regime never exercised"
    assert (weights.loc[nonzero, "SPY"] == 0.40).any(), "Moderate regime never exercised"
    assert (weights.loc[nonzero, "SPY"] == 0.05).any(), "High regime never exercised"
