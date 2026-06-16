"""Integration tests for curve_butterfly_2s5s10s.

Mocks ``FREDAdapter.fetch`` to return synthetic ``DGS2``, ``DGS5``,
``DGS10`` yield series, derives 3-leg bond price proxies via the
duration approximation, runs the strategy through the vectorbt bridge.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.rates.fred_adapter import FREDAdapter
from alphakit.strategies.rates.curve_butterfly_2s5s10s.strategy import CurveButterfly2s5s10s

_DURATION_2Y = 1.95
_DURATION_5Y = 4.5
_DURATION_10Y = 8.0


def _synthetic_yields(seed: int = 42, years: float = 6) -> pd.DataFrame:
    """Synthetic 2Y/5Y/10Y yields with a slowly-varying curvature."""
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    parallel = 3.0 + np.cumsum(rng.normal(0.0, 0.04, size=n_days)) * 0.5
    slope = 1.5 + np.cumsum(rng.normal(0.0, 0.02, size=n_days)) * 0.5
    curvature = np.cumsum(rng.normal(0.0, 0.01, size=n_days)) * 0.3

    parallel = np.clip(parallel, 0.5, 7.0)
    slope = np.clip(slope, -0.5, 3.5)

    dgs2 = parallel - slope / 2.0
    dgs10 = parallel + slope / 2.0
    dgs5 = (dgs2 + dgs10) / 2.0 + curvature
    dgs2 = np.clip(dgs2, 0.05, None)
    dgs5 = np.clip(dgs5, 0.05, None)
    return pd.DataFrame({"DGS2": dgs2, "DGS5": dgs5, "DGS10": dgs10}, index=index)


def _yields_to_three_leg_prices(yields_pct: pd.DataFrame) -> pd.DataFrame:
    yields_decimal = yields_pct / 100.0
    dr2 = -_DURATION_2Y * yields_decimal["DGS2"].diff().fillna(0.0)
    dr5 = -_DURATION_5Y * yields_decimal["DGS5"].diff().fillna(0.0)
    dr10 = -_DURATION_10Y * yields_decimal["DGS10"].diff().fillna(0.0)
    return pd.DataFrame(
        {
            "DGS2_proxy": 100.0 * np.exp(dr2.cumsum()),
            "DGS5_proxy": 100.0 * np.exp(dr5.cumsum()),
            "DGS10_proxy": 100.0 * np.exp(dr10.cumsum()),
        },
        index=yields_pct.index,
    )


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_fred() -> None:
    fred_response = _synthetic_yields(seed=42, years=6)

    with patch.object(FREDAdapter, "fetch", return_value=fred_response):
        adapter = FREDAdapter()
        yields = adapter.fetch(
            symbols=["DGS2", "DGS5", "DGS10"],
            start=datetime(2018, 1, 1),
            end=datetime(2024, 1, 1),
        )

    prices = _yields_to_three_leg_prices(yields)
    strategy = CurveButterfly2s5s10s()
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)

    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "curve_butterfly_2s5s10s"
    assert result.meta["paper_doi"] == "10.3905/jfi.1991.692347"
    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics
        assert np.isfinite(result.metrics[key])
    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_fred() -> None:
    fred_response = _synthetic_yields(seed=123, years=5)

    with patch.object(FREDAdapter, "fetch", return_value=fred_response):
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

    pa = _yields_to_three_leg_prices(ya)
    pb = _yields_to_three_leg_prices(yb)
    strategy = CurveButterfly2s5s10s()
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
        vectorbt_bridge.run(strategy=CurveButterfly2s5s10s(), prices=empty)
