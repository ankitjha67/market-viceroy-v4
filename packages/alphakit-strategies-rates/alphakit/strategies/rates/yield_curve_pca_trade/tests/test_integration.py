"""Integration tests for yield_curve_pca_trade."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.rates.fred_adapter import FREDAdapter
from alphakit.strategies.rates.yield_curve_pca_trade.strategy import YieldCurvePCATrade

_DURATIONS = {
    "DGS2": 1.95,
    "DGS3": 2.85,
    "DGS5": 4.5,
    "DGS7": 6.0,
    "DGS10": 8.0,
}


def _synthetic_yield_panel(seed: int = 42, years: float = 8) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    # Three-factor curve: parallel + slope + curvature, plus per-bond noise.
    parallel = 3.0 + np.cumsum(rng.normal(0.0, 0.04, size=n)) * 0.5
    slope = 1.5 + np.cumsum(rng.normal(0.0, 0.02, size=n)) * 0.5
    curvature = np.cumsum(rng.normal(0.0, 0.01, size=n)) * 0.3
    parallel = np.clip(parallel, 0.5, 7.0)
    slope = np.clip(slope, -0.5, 3.5)

    # Curve weights for each maturity bucket
    curve_w = {
        "DGS2": (1.0, -0.5, -0.3),
        "DGS3": (1.0, -0.3, -0.1),
        "DGS5": (1.0, 0.0, 0.7),
        "DGS7": (1.0, 0.3, 0.1),
        "DGS10": (1.0, 0.5, -0.3),
    }
    yields = {}
    for sym, (lvl, sl, cv) in curve_w.items():
        idiosyncratic = rng.normal(0.0, 0.05, size=n).cumsum() * 0.1
        y = lvl * parallel + sl * slope / 2.0 + cv * curvature + idiosyncratic
        yields[sym] = np.clip(y, 0.05, 9.0)
    return pd.DataFrame(yields, index=index)


def _yields_to_prices(y: pd.DataFrame) -> pd.DataFrame:
    yd = y / 100.0
    return pd.DataFrame(
        {
            f"{sym}_proxy": 100.0 * np.exp((-_DURATIONS[sym] * yd[sym].diff().fillna(0.0)).cumsum())
            for sym in y.columns
        },
        index=y.index,
    )


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_fred() -> None:
    fred_resp = _synthetic_yield_panel(seed=42, years=8)
    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        y = adapter.fetch(
            symbols=list(_DURATIONS.keys()),
            start=datetime(2018, 1, 1),
            end=datetime(2026, 1, 1),
        )

    prices = _yields_to_prices(y)
    result = vectorbt_bridge.run(strategy=YieldCurvePCATrade(), prices=prices)

    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "yield_curve_pca_trade"
    assert result.meta["paper_doi"] == "10.3905/jfi.1991.692347"
    for k in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert k in result.metrics
        assert np.isfinite(result.metrics[k])
    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_fred() -> None:
    fred_resp = _synthetic_yield_panel(seed=123, years=6)
    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        y = adapter.fetch(
            symbols=list(_DURATIONS.keys()),
            start=datetime(2018, 1, 1),
            end=datetime(2024, 1, 1),
        )
    prices = _yields_to_prices(y)
    ra = vectorbt_bridge.run(strategy=YieldCurvePCATrade(), prices=prices)
    rb = vectorbt_bridge.run(strategy=YieldCurvePCATrade(), prices=prices)
    pd.testing.assert_frame_equal(ra.weights, rb.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=[f"{c}_proxy" for c in _DURATIONS],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=YieldCurvePCATrade(), prices=empty)
