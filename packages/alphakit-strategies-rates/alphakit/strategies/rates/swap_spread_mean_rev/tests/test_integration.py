"""Integration tests for swap_spread_mean_rev."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.rates.fred_adapter import FREDAdapter
from alphakit.strategies.rates.swap_spread_mean_rev.strategy import SwapSpreadMeanRev


def _synthetic_treasury_swap(seed: int = 42, years: float = 6) -> pd.DataFrame:
    """Synthetic Treasury yield + swap rate with mean-reverting spread."""
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    treasury = 3.0 + np.cumsum(rng.normal(0.0, 0.04, size=n)) * 0.5
    spread_bps = 30.0 + np.cumsum(rng.normal(0.0, 1.5, size=n)) * 0.3
    spread_bps = np.clip(spread_bps, -50.0, 200.0)
    swap = treasury + spread_bps / 100.0
    treasury = np.clip(treasury, 0.5, 7.0)
    swap = np.clip(swap, 0.5, 8.0)
    return pd.DataFrame({"DGS10": treasury, "SWAP10Y": swap}, index=index)


def _yields_to_prices(y: pd.DataFrame) -> pd.DataFrame:
    yd = y / 100.0
    duration = 8.0
    return pd.DataFrame(
        {
            "IEF_proxy": 100.0 * np.exp((-duration * yd["DGS10"].diff().fillna(0.0)).cumsum()),
            "IRS_10Y_proxy": 100.0
            * np.exp((-duration * yd["SWAP10Y"].diff().fillna(0.0)).cumsum()),
        },
        index=y.index,
    )


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_fred() -> None:
    fred_resp = _synthetic_treasury_swap(seed=42, years=6)
    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        y = adapter.fetch(
            symbols=["DGS10", "SWAP10Y"],
            start=datetime(2018, 1, 1),
            end=datetime(2024, 1, 1),
        )

    prices = _yields_to_prices(y)
    result = vectorbt_bridge.run(strategy=SwapSpreadMeanRev(), prices=prices)

    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "swap_spread_mean_rev"
    assert result.meta["paper_doi"] == "10.1093/rfs/hhl026"
    for k in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert k in result.metrics
        assert np.isfinite(result.metrics[k])
    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_fred() -> None:
    fred_resp = _synthetic_treasury_swap(seed=123, years=5)
    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        y = adapter.fetch(
            symbols=["DGS10", "SWAP10Y"],
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
    prices = _yields_to_prices(y)
    ra = vectorbt_bridge.run(strategy=SwapSpreadMeanRev(), prices=prices)
    rb = vectorbt_bridge.run(strategy=SwapSpreadMeanRev(), prices=prices)
    pd.testing.assert_frame_equal(ra.weights, rb.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["IEF_proxy", "IRS_10Y_proxy"],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=SwapSpreadMeanRev(), prices=empty)
