"""Integration tests for g10_bond_carry."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.rates.fred_adapter import FREDAdapter
from alphakit.strategies.rates.g10_bond_carry.strategy import G10BondCarry

# IRLTLT01 = "long-term government bond yield" by country (FRED).
_COUNTRY_SYMBOLS = ["IRLTLT01USM156N", "IRLTLT01DEM156N", "IRLTLT01JPM156N"]
_DURATION_DEFAULTS = {
    "IRLTLT01USM156N_proxy": 8.0,
    "IRLTLT01DEM156N_proxy": 8.8,
    "IRLTLT01JPM156N_proxy": 9.5,
}


def _synthetic_country_yields(seed: int = 42, years: float = 6) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    us = 3.0 + np.cumsum(rng.normal(0.0, 0.04, size=n)) * 0.5
    de = us - 1.0 + np.cumsum(rng.normal(0.0, 0.02, size=n)) * 0.3
    jp = 0.5 + np.cumsum(rng.normal(0.0, 0.01, size=n)) * 0.2
    us = np.clip(us, 0.5, 7.0)
    de = np.clip(de, -0.5, 5.0)
    jp = np.clip(jp, -0.5, 2.5)
    return pd.DataFrame(
        {"IRLTLT01USM156N": us, "IRLTLT01DEM156N": de, "IRLTLT01JPM156N": jp},
        index=index,
    )


def _yields_to_prices(y: pd.DataFrame) -> pd.DataFrame:
    yd = y / 100.0
    durations = {"IRLTLT01USM156N": 8.0, "IRLTLT01DEM156N": 8.8, "IRLTLT01JPM156N": 9.5}
    return pd.DataFrame(
        {
            f"{sym}_proxy": 100.0 * np.exp((-durations[sym] * yd[sym].diff().fillna(0.0)).cumsum())
            for sym in y.columns
        },
        index=y.index,
    )


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_fred() -> None:
    fred_resp = _synthetic_country_yields(seed=42, years=6)
    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        y = adapter.fetch(
            symbols=_COUNTRY_SYMBOLS,
            start=datetime(2018, 1, 1),
            end=datetime(2024, 1, 1),
        )

    prices = _yields_to_prices(y)
    strategy = G10BondCarry(durations=_DURATION_DEFAULTS)
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)

    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "g10_bond_carry"
    assert result.meta["paper_doi"] == "10.1111/jofi.12021"
    for k in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert k in result.metrics
        assert np.isfinite(result.metrics[k])
    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_fred() -> None:
    fred_resp = _synthetic_country_yields(seed=123, years=5)
    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        y = adapter.fetch(
            symbols=_COUNTRY_SYMBOLS,
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
    prices = _yields_to_prices(y)
    strategy = G10BondCarry(durations=_DURATION_DEFAULTS)
    ra = vectorbt_bridge.run(strategy=strategy, prices=prices)
    rb = vectorbt_bridge.run(strategy=strategy, prices=prices)
    pd.testing.assert_frame_equal(ra.weights, rb.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=[f"{c}_proxy" for c in _COUNTRY_SYMBOLS],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=G10BondCarry(durations=_DURATION_DEFAULTS), prices=empty)
