"""Integration tests for global_inflation_momentum."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.rates.fred_adapter import FREDAdapter
from alphakit.strategies.rates.global_inflation_momentum.strategy import (
    GlobalInflationMomentum,
)


def _synthetic_paired_panel(seed: int = 42, years: float = 6) -> pd.DataFrame:
    """Synthetic CPI + bond panel for 3 countries (US/DE/JP)."""
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    out: dict[str, np.ndarray] = {}
    for label, (cpi_drift_annual, bond_drift_annual) in {
        "US": (0.025, 0.02),
        "DE": (0.020, 0.02),
        "JP": (0.005, 0.01),
    }.items():
        cpi_path = 100.0 * np.exp(
            cpi_drift_annual / 252.0 * np.arange(n) + np.cumsum(rng.normal(0.0, 0.001, size=n))
        )
        bond_path = 100.0 * np.exp(
            bond_drift_annual / 252.0 * np.arange(n) + np.cumsum(rng.normal(0.0, 0.005, size=n))
        )
        out[f"CPI_{label}"] = cpi_path
        out[f"BOND_{label}"] = bond_path
    return pd.DataFrame(out, index=index)


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_fred() -> None:
    fred_resp = _synthetic_paired_panel(seed=42, years=6)

    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        prices = adapter.fetch(
            symbols=list(fred_resp.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2024, 1, 1),
        )

    result = vectorbt_bridge.run(strategy=GlobalInflationMomentum(), prices=prices)

    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "global_inflation_momentum"
    assert result.meta["paper_doi"] == "10.3905/jpm.2014.40.3.087"
    for k in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert k in result.metrics
        assert np.isfinite(result.metrics[k])
    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_fred() -> None:
    fred_resp = _synthetic_paired_panel(seed=123, years=5)
    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        pa = adapter.fetch(
            symbols=list(fred_resp.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
        pb = adapter.fetch(
            symbols=list(fred_resp.columns),
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
    ra = vectorbt_bridge.run(strategy=GlobalInflationMomentum(), prices=pa)
    rb = vectorbt_bridge.run(strategy=GlobalInflationMomentum(), prices=pb)
    pd.testing.assert_frame_equal(ra.weights, rb.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["CPI_US", "BOND_US", "CPI_DE", "BOND_DE"],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=GlobalInflationMomentum(), prices=empty)
