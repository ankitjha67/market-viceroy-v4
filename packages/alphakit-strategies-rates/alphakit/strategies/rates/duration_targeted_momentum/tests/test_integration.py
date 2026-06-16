"""Integration tests for duration_targeted_momentum."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.rates.fred_adapter import FREDAdapter
from alphakit.strategies.rates.duration_targeted_momentum.strategy import (
    DurationTargetedMomentum,
)

_DURATIONS = {"DGS2_proxy": 1.95, "DGS5_proxy": 4.5, "DGS10_proxy": 8.0}


def _synthetic_yields(seed: int = 42, years: float = 6) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    parallel = 3.0 + np.cumsum(rng.normal(0.0, 0.04, size=n)) * 0.5
    slope = 1.5 + np.cumsum(rng.normal(0.0, 0.02, size=n)) * 0.5
    curvature = np.cumsum(rng.normal(0.0, 0.01, size=n)) * 0.3
    parallel = np.clip(parallel, 0.5, 7.0)
    slope = np.clip(slope, -0.5, 3.5)
    dgs2 = parallel - slope / 2.0
    dgs10 = parallel + slope / 2.0
    dgs5 = (dgs2 + dgs10) / 2.0 + curvature
    dgs2 = np.clip(dgs2, 0.05, None)
    dgs5 = np.clip(dgs5, 0.05, None)
    return pd.DataFrame({"DGS2": dgs2, "DGS5": dgs5, "DGS10": dgs10}, index=index)


def _yields_to_prices(y: pd.DataFrame) -> pd.DataFrame:
    yd = y / 100.0
    return pd.DataFrame(
        {
            "DGS2_proxy": 100.0 * np.exp((-1.95 * yd["DGS2"].diff().fillna(0.0)).cumsum()),
            "DGS5_proxy": 100.0 * np.exp((-4.5 * yd["DGS5"].diff().fillna(0.0)).cumsum()),
            "DGS10_proxy": 100.0 * np.exp((-8.0 * yd["DGS10"].diff().fillna(0.0)).cumsum()),
        },
        index=y.index,
    )


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_fred() -> None:
    fred_resp = _synthetic_yields(seed=42, years=6)
    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        y = adapter.fetch(
            symbols=["DGS2", "DGS5", "DGS10"],
            start=datetime(2018, 1, 1),
            end=datetime(2024, 1, 1),
        )

    prices = _yields_to_prices(y)
    strategy = DurationTargetedMomentum(durations=_DURATIONS)
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)

    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "duration_targeted_momentum"
    assert result.meta["paper_doi"] == "10.17016/FEDS.2015.103"
    for k in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert k in result.metrics
        assert np.isfinite(result.metrics[k])
    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_fred() -> None:
    fred_resp = _synthetic_yields(seed=123, years=5)
    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        ya = adapter.fetch(
            symbols=["DGS2", "DGS5", "DGS10"],
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
        yb = adapter.fetch(
            symbols=["DGS2", "DGS5", "DGS10"],
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
    pa = _yields_to_prices(ya)
    pb = _yields_to_prices(yb)
    strategy = DurationTargetedMomentum(durations=_DURATIONS)
    ra = vectorbt_bridge.run(strategy=strategy, prices=pa)
    rb = vectorbt_bridge.run(strategy=strategy, prices=pb)
    pd.testing.assert_frame_equal(ra.weights, rb.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["DGS2_proxy", "DGS5_proxy", "DGS10_proxy"],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=DurationTargetedMomentum(durations=_DURATIONS), prices=empty)
