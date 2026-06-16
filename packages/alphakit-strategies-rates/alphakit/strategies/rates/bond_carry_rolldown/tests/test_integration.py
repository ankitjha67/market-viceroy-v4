"""Integration tests for bond_carry_rolldown."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.rates.fred_adapter import FREDAdapter
from alphakit.strategies.rates.bond_carry_rolldown.strategy import BondCarryRolldown

_DURATION_2Y = 1.95
_DURATION_10Y = 8.0


def _synthetic_yields(seed: int = 42, years: float = 6) -> pd.DataFrame:
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


def _yields_to_prices(y: pd.DataFrame) -> pd.DataFrame:
    yd = y / 100.0
    sr = -_DURATION_2Y * yd["DGS2"].diff().fillna(0.0)
    lr = -_DURATION_10Y * yd["DGS10"].diff().fillna(0.0)
    return pd.DataFrame(
        {"SHY_proxy": 100.0 * np.exp(sr.cumsum()), "TLT_proxy": 100.0 * np.exp(lr.cumsum())},
        index=y.index,
    )


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_fred() -> None:
    fred_resp = _synthetic_yields(seed=42, years=6)
    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        y = adapter.fetch(
            symbols=["DGS2", "DGS10"], start=datetime(2018, 1, 1), end=datetime(2024, 1, 1)
        )

    prices = _yields_to_prices(y)
    result = vectorbt_bridge.run(strategy=BondCarryRolldown(), prices=prices)

    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "bond_carry_rolldown"
    assert result.meta["paper_doi"] == "10.1016/j.jfineco.2017.11.002"
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
            symbols=["DGS2", "DGS10"], start=datetime(2018, 1, 1), end=datetime(2023, 1, 1)
        )
        yb = adapter.fetch(
            symbols=["DGS2", "DGS10"], start=datetime(2018, 1, 1), end=datetime(2023, 1, 1)
        )
    pa = _yields_to_prices(ya)
    pb = _yields_to_prices(yb)
    ra = vectorbt_bridge.run(strategy=BondCarryRolldown(), prices=pa)
    rb = vectorbt_bridge.run(strategy=BondCarryRolldown(), prices=pb)
    pd.testing.assert_frame_equal(ra.weights, rb.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["SHY_proxy", "TLT_proxy"],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=BondCarryRolldown(), prices=empty)
