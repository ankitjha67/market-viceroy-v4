"""Integration tests for yield_curve_regime_allocation.

Mocks ``YFinanceAdapter.fetch`` for the 3 tradable ETFs; the two
FRED informational yield columns (DGS10, DGS2) are constructed
inline and cycle through all 3 yield-curve regimes (steep / flat /
inverted). Runs the strategy through the vectorbt bridge and asserts
the returned :class:`BacktestResult` is internally consistent,
including the two-informational-column zero-weight invariant.

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
from alphakit.strategies.macro.yield_curve_regime_allocation.strategy import (
    YieldCurveRegimeAllocation,
)


def _synthetic_panel(seed: int = 42, years: float = 6) -> pd.DataFrame:
    """5-column panel: 3 tradable ETFs + 2 informational yield columns.

    DGS10 cycles through three regimes in ~2-year blocks:
    - Steep  (DGS10 - DGS2 ≈ +2%): 2018-2019
    - Flat   (DGS10 - DGS2 ≈ +0.4%): 2020-2021
    - Inverted (DGS10 - DGS2 ≈ -0.5%): 2022-2023

    All yield levels are strictly positive (bridge constraint: both
    DGS10 and DGS2 carry a term premium even in ZIRP environments).
    """
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    spy = 100.0 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, size=n_days)))
    tlt = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.010, size=n_days)))
    gld = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.010, size=n_days)))

    # Yield columns: construct slopes that cycle through all 3 regimes.
    # DGS2 stays positive at 1.0%; DGS10 varies the slope.
    dgs2 = np.full(n_days, 1.0)  # 2-year yield ≈ 1%, strictly > 0

    # ~2-year blocks: steep → flat → inverted (2-year blocks each).
    block = round(2.0 * 252)
    slope_target = np.empty(n_days, dtype=float)
    for i in range(0, n_days, block):
        end = min(i + block, n_days)
        block_idx = i // block
        if block_idx % 3 == 0:
            slope_target[i:end] = 2.0  # steep (slope >= 1.0%)
        elif block_idx % 3 == 1:
            slope_target[i:end] = 0.4  # flat  (0.0 <= slope < 1.0%)
        else:
            slope_target[i:end] = -0.5  # inverted (slope < 0.0%)

    dgs10 = dgs2 + slope_target  # DGS10 = DGS2 + slope_target
    # Clamp DGS10 > 0.0 (never negative; in practice DGS10 > DGS2 or close).
    dgs10 = np.maximum(dgs10, 0.05)

    return pd.DataFrame(
        {
            "SPY": spy,
            "TLT": tlt,
            "GLD": gld,
            "DGS10": dgs10,
            "DGS2": dgs2,
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

    strategy = YieldCurveRegimeAllocation()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "yield_curve_regime_allocation"
    assert result.meta["paper_doi"] == "10.1016/j.jfineco.2005.05.005"

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics
        assert np.isfinite(result.metrics[key])

    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_both_informational_columns_zero_through_bridge() -> None:
    """DGS10 and DGS2 must carry exactly 0.0 weight in the backtest output."""
    panel = _synthetic_panel(seed=7, years=5)

    with patch.object(YFinanceAdapter, "fetch", return_value=panel):
        adapter = YFinanceAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )

    strategy = YieldCurveRegimeAllocation()
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)

    assert (result.weights["DGS10"] == 0.0).all()
    assert (result.weights["DGS2"] == 0.0).all()


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

    strategy = YieldCurveRegimeAllocation()
    result_a = vectorbt_bridge.run(strategy=strategy, prices=prices_a)
    result_b = vectorbt_bridge.run(strategy=strategy, prices=prices_b)
    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    pd.testing.assert_frame_equal(result_a.weights, result_b.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    """Passing an empty DataFrame raises ValueError with 'empty' in the message."""
    cols = ["SPY", "TLT", "GLD", "DGS10", "DGS2"]
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=cols, dtype=float)
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=YieldCurveRegimeAllocation(), prices=empty)


@pytest.mark.integration
def test_all_three_regimes_are_exercised() -> None:
    """The synthetic panel exercises steep / flat / inverted regimes."""
    panel = _synthetic_panel(seed=42, years=6)

    strategy = YieldCurveRegimeAllocation()
    weights = strategy.generate_signals(panel)

    # Steep regime: SPY weight ≈ 0.70 (equity-heavy).
    steep_mask = weights["SPY"] > 0.5
    # Flat regime: SPY weight ≈ 0.40.
    flat_mask = (weights["SPY"] > 0.30) & (weights["SPY"] < 0.50)
    # Inverted regime: SPY weight ≈ 0.00.
    inverted_mask = weights["SPY"] == 0.0

    # Each regime must appear at least once (excluding zero warm-up rows).
    nonzero = weights["TLT"] > 0
    assert steep_mask[nonzero].any(), "steep regime never exercised"
    assert flat_mask[nonzero].any(), "flat regime never exercised"
    assert inverted_mask[nonzero].any(), "inverted regime never exercised"
