"""Integration tests for curve_flattener_2s10s.

Mirror of the steepener integration tests: mock FRED, derive bond
proxies via duration approximation, run via vectorbt bridge, assert
result is internally consistent.
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
from alphakit.strategies.rates.curve_flattener_2s10s.strategy import CurveFlattener2s10s

_TWO_YEAR_DURATION = 1.95
_TEN_YEAR_DURATION = 8.0


def _synthetic_dgs2_dgs10(seed: int = 42, years: float = 6) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")
    parallel = 3.0 + np.cumsum(rng.normal(0.0, 0.04, size=n_days)) * 0.5
    spread = 1.5 + np.cumsum(rng.normal(0.0, 0.02, size=n_days)) * 0.5
    parallel = np.clip(parallel, 0.5, 7.0)
    spread = np.clip(spread, -0.5, 3.5)
    dgs10 = parallel + spread / 2.0
    dgs2 = np.clip(parallel - spread / 2.0, 0.05, None)
    return pd.DataFrame({"DGS2": dgs2, "DGS10": dgs10}, index=index)


def _yields_to_two_leg_prices(yields_pct: pd.DataFrame) -> pd.DataFrame:
    yields_decimal = yields_pct / 100.0
    short_returns = -_TWO_YEAR_DURATION * yields_decimal["DGS2"].diff().fillna(0.0)
    long_returns = -_TEN_YEAR_DURATION * yields_decimal["DGS10"].diff().fillna(0.0)
    short_prices = 100.0 * np.exp(short_returns.cumsum())
    long_prices = 100.0 * np.exp(long_returns.cumsum())
    return pd.DataFrame(
        {"SHY_proxy": short_prices, "TLT_proxy": long_prices},
        index=yields_pct.index,
    )


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_fred() -> None:
    fred_response = _synthetic_dgs2_dgs10(seed=42, years=6)

    with patch.object(FREDAdapter, "fetch", return_value=fred_response):
        adapter = FREDAdapter()
        yields = adapter.fetch(
            symbols=["DGS2", "DGS10"],
            start=datetime(2018, 1, 1),
            end=datetime(2024, 1, 1),
        )

    prices = _yields_to_two_leg_prices(yields)
    strategy = CurveFlattener2s10s()
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)

    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "curve_flattener_2s10s"
    assert result.meta["paper_doi"] == "10.1257/0002828053828581"

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics
        assert np.isfinite(result.metrics[key])
    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_fred() -> None:
    fred_response = _synthetic_dgs2_dgs10(seed=123, years=5)

    with patch.object(FREDAdapter, "fetch", return_value=fred_response):
        adapter = FREDAdapter()
        yields_a = adapter.fetch(
            symbols=["DGS2", "DGS10"], start=datetime(2018, 1, 1), end=datetime(2023, 1, 1)
        )
        yields_b = adapter.fetch(
            symbols=["DGS2", "DGS10"], start=datetime(2018, 1, 1), end=datetime(2023, 1, 1)
        )

    prices_a = _yields_to_two_leg_prices(yields_a)
    prices_b = _yields_to_two_leg_prices(yields_b)

    strategy = CurveFlattener2s10s()
    result_a = vectorbt_bridge.run(strategy=strategy, prices=prices_a)
    result_b = vectorbt_bridge.run(strategy=strategy, prices=prices_b)

    pd.testing.assert_frame_equal(result_a.weights, result_b.weights)
    for key, value in result_a.metrics.items():
        assert result_b.metrics[key] == pytest.approx(value)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["SHY_proxy", "TLT_proxy"],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=CurveFlattener2s10s(), prices=empty)
