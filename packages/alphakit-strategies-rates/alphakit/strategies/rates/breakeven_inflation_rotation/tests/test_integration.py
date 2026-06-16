"""Integration tests for breakeven_inflation_rotation."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.rates.fred_adapter import FREDAdapter
from alphakit.strategies.rates.breakeven_inflation_rotation.strategy import (
    BreakevenInflationRotation,
)

_DURATION_TIPS = 7.5
_DURATION_NOMINAL = 8.0


def _synthetic_yields(seed: int = 42, years: float = 6) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    nominal_path = 3.0 + np.cumsum(rng.normal(0.0, 0.04, size=n)) * 0.5
    breakeven_path = 2.0 + np.cumsum(rng.normal(0.0, 0.02, size=n)) * 0.5
    nominal_path = np.clip(nominal_path, 0.5, 7.0)
    breakeven_path = np.clip(breakeven_path, 0.0, 4.0)
    tips_yield = nominal_path - breakeven_path
    tips_yield = np.clip(tips_yield, -1.0, 6.0)
    return pd.DataFrame({"DGS10": nominal_path, "DFII10": tips_yield}, index=index)


def _yields_to_prices(y: pd.DataFrame) -> pd.DataFrame:
    yd = y / 100.0
    nom_ret = -_DURATION_NOMINAL * yd["DGS10"].diff().fillna(0.0)
    tips_ret = -_DURATION_TIPS * yd["DFII10"].diff().fillna(0.0)
    return pd.DataFrame(
        {
            "TIP_proxy": 100.0 * np.exp(tips_ret.cumsum()),
            "IEF_proxy": 100.0 * np.exp(nom_ret.cumsum()),
        },
        index=y.index,
    )


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_fred() -> None:
    fred_resp = _synthetic_yields(seed=42, years=6)
    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        y = adapter.fetch(
            symbols=["DGS10", "DFII10"],
            start=datetime(2018, 1, 1),
            end=datetime(2024, 1, 1),
        )

    prices = _yields_to_prices(y)
    result = vectorbt_bridge.run(strategy=BreakevenInflationRotation(), prices=prices)

    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "breakeven_inflation_rotation"
    assert result.meta["paper_doi"] == "10.1111/jofi.12032"
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
            symbols=["DGS10", "DFII10"],
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
        yb = adapter.fetch(
            symbols=["DGS10", "DFII10"],
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
    pa = _yields_to_prices(ya)
    pb = _yields_to_prices(yb)
    ra = vectorbt_bridge.run(strategy=BreakevenInflationRotation(), prices=pa)
    rb = vectorbt_bridge.run(strategy=BreakevenInflationRotation(), prices=pb)
    pd.testing.assert_frame_equal(ra.weights, rb.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["TIP_proxy", "IEF_proxy"],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=BreakevenInflationRotation(), prices=empty)
