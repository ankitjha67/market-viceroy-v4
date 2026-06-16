"""Integration tests for fed_policy_tilt.

Mocks ``YFinanceAdapter.fetch`` for the 3 tradable ETFs; the
FEDFUNDS informational column is constructed inline and cycles
through tightening and easing regimes. Runs the strategy through
the vectorbt bridge and asserts the returned :class:`BacktestResult`
is internally consistent, including the informational-column
zero-weight invariant.

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
from alphakit.strategies.macro.fed_policy_tilt.strategy import FedPolicyTilt


def _synthetic_panel(seed: int = 42, years: float = 6) -> pd.DataFrame:
    """4-column panel: 3 tradable ETFs + 1 FEDFUNDS informational column.

    FEDFUNDS cycles through tightening and easing regimes in ~2-year
    blocks, exercising both cells of the 2-cell classification.
    All FEDFUNDS values are strictly positive (FEDFUNDS never prints
    exactly 0.0 — monthly averages carry a small positive value even
    in ZIRP environments).
    """
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    spy = 100.0 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, size=n_days)))
    tlt = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.010, size=n_days)))
    gld = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.010, size=n_days)))

    # FEDFUNDS: tightening (rising) for first 3 years, easing (falling) for last 3.
    half = n_days // 2
    # Tightening: 0.5 → 2.5% linear rise.
    # Easing: 2.5 → 0.5% linear fall.
    tightening_vals = np.linspace(0.5, 2.5, half)
    easing_vals = np.linspace(2.5, 0.5, n_days - half)
    fedfunds = np.concatenate([tightening_vals, easing_vals])
    # Clamp > 0 (FEDFUNDS always strictly positive).
    fedfunds = np.maximum(fedfunds, 0.07)

    return pd.DataFrame(
        {
            "SPY": spy,
            "TLT": tlt,
            "GLD": gld,
            "FEDFUNDS": fedfunds,
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

    strategy = FedPolicyTilt()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "fed_policy_tilt"
    assert result.meta["paper_doi"] == "10.1016/0304-405X(96)00875-X"

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics
        assert np.isfinite(result.metrics[key])

    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_informational_column_zero_through_bridge() -> None:
    """FEDFUNDS must carry exactly 0.0 weight in the backtest output."""
    panel = _synthetic_panel(seed=7, years=5)

    with patch.object(YFinanceAdapter, "fetch", return_value=panel):
        adapter = YFinanceAdapter()
        prices = adapter.fetch(
            symbols=list(panel.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )

    strategy = FedPolicyTilt()
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)

    assert (result.weights["FEDFUNDS"] == 0.0).all()


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

    strategy = FedPolicyTilt()
    result_a = vectorbt_bridge.run(strategy=strategy, prices=prices_a)
    result_b = vectorbt_bridge.run(strategy=strategy, prices=prices_b)
    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    pd.testing.assert_frame_equal(result_a.weights, result_b.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    """Passing an empty DataFrame raises ValueError with 'empty' in the message."""
    cols = ["SPY", "TLT", "GLD", "FEDFUNDS"]
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=cols, dtype=float)
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=FedPolicyTilt(), prices=empty)


@pytest.mark.integration
def test_both_regimes_exercised_in_backtest() -> None:
    """The synthetic panel exercises both tightening and easing regimes."""
    panel = _synthetic_panel(seed=42, years=6)

    strategy = FedPolicyTilt()
    weights = strategy.generate_signals(panel)

    # Tightening: SPY=0.20. Easing: SPY=0.70.
    nonzero = weights["TLT"] > 0
    assert (weights.loc[nonzero, "SPY"] < 0.5).any(), "Tightening regime never exercised"
    assert (weights.loc[nonzero, "SPY"] > 0.5).any(), "Easing regime never exercised"
