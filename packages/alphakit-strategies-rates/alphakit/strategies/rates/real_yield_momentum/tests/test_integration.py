"""Integration tests for real_yield_momentum."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.rates.fred_adapter import FREDAdapter
from alphakit.strategies.rates.real_yield_momentum.strategy import RealYieldMomentum

_TIPS_DURATION = 7.5


def _synthetic_dfii10(seed: int = 42, years: float = 6) -> pd.Series:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    yields = 1.0 + np.cumsum(rng.normal(0.0, 0.03, size=n)) * 0.5
    yields = np.clip(yields, -1.0, 4.0)
    return pd.Series(yields, index=index, name="DFII10")


def _yields_to_prices(yields_pct: pd.Series) -> pd.DataFrame:
    yd = yields_pct / 100.0
    daily_returns = -_TIPS_DURATION * yd.diff().fillna(0.0)
    return pd.DataFrame(
        {"TIP_proxy": 100.0 * np.exp(daily_returns.cumsum())},
        index=yields_pct.index,
    )


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_fred() -> None:
    fred_resp = pd.DataFrame({"DFII10": _synthetic_dfii10(seed=42, years=6)})
    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        y = adapter.fetch(symbols=["DFII10"], start=datetime(2018, 1, 1), end=datetime(2024, 1, 1))

    prices = _yields_to_prices(y["DFII10"])
    result = vectorbt_bridge.run(strategy=RealYieldMomentum(), prices=prices)

    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "real_yield_momentum"
    assert result.meta["paper_doi"] == "10.1111/jofi.12021"
    for k in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert k in result.metrics
        assert np.isfinite(result.metrics[k])
    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_fred() -> None:
    fred_resp = pd.DataFrame({"DFII10": _synthetic_dfii10(seed=123, years=5)})
    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        y = adapter.fetch(symbols=["DFII10"], start=datetime(2018, 1, 1), end=datetime(2023, 1, 1))
    prices = _yields_to_prices(y["DFII10"])
    ra = vectorbt_bridge.run(strategy=RealYieldMomentum(), prices=prices)
    rb = vectorbt_bridge.run(strategy=RealYieldMomentum(), prices=prices)
    pd.testing.assert_frame_equal(ra.weights, rb.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["TIP_proxy"], dtype=float)
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=RealYieldMomentum(), prices=empty)
