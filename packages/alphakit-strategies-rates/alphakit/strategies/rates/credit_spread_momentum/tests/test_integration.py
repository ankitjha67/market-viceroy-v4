"""Integration tests for credit_spread_momentum."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.rates.fred_adapter import FREDAdapter
from alphakit.strategies.rates.credit_spread_momentum.strategy import CreditSpreadMomentum


def _synthetic_oas(seed: int = 42, years: float = 6) -> pd.Series:
    """Synthetic IG OAS (BAMLC0A0CM) series in basis points."""
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    oas_bps = 120.0 + np.cumsum(rng.normal(0.0, 1.5, size=n)) * 0.3
    oas_bps = np.clip(oas_bps, 50.0, 500.0)
    return pd.Series(oas_bps, index=index, name="BAMLC0A0CM")


def _oas_to_lqd_proxy(oas_bps: pd.Series) -> pd.DataFrame:
    """Convert OAS (in bps) to an LQD-like price proxy.

    Approximation: LQD's effective duration ≈ 8 years; price moves
    inversely to OAS via the duration relationship.
    """
    duration = 8.0
    daily_returns = -duration * (oas_bps / 10_000.0).diff().fillna(0.0)
    return pd.DataFrame(
        {"LQD_proxy": 100.0 * np.exp(daily_returns.cumsum())},
        index=oas_bps.index,
    )


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_fred() -> None:
    fred_resp = pd.DataFrame({"BAMLC0A0CM": _synthetic_oas(seed=42, years=6)})
    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        oas = adapter.fetch(
            symbols=["BAMLC0A0CM"],
            start=datetime(2018, 1, 1),
            end=datetime(2024, 1, 1),
        )

    prices = _oas_to_lqd_proxy(oas["BAMLC0A0CM"])
    result = vectorbt_bridge.run(strategy=CreditSpreadMomentum(), prices=prices)

    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "credit_spread_momentum"
    assert result.meta["paper_doi"] == "10.1093/rfs/hht022"
    for k in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert k in result.metrics
        assert np.isfinite(result.metrics[k])
    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_fred() -> None:
    fred_resp = pd.DataFrame({"BAMLC0A0CM": _synthetic_oas(seed=123, years=5)})
    with patch.object(FREDAdapter, "fetch", return_value=fred_resp):
        adapter = FREDAdapter()
        oas = adapter.fetch(
            symbols=["BAMLC0A0CM"],
            start=datetime(2018, 1, 1),
            end=datetime(2023, 1, 1),
        )
    prices = _oas_to_lqd_proxy(oas["BAMLC0A0CM"])
    ra = vectorbt_bridge.run(strategy=CreditSpreadMomentum(), prices=prices)
    rb = vectorbt_bridge.run(strategy=CreditSpreadMomentum(), prices=prices)
    pd.testing.assert_frame_equal(ra.weights, rb.weights)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["LQD_proxy"], dtype=float)
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=CreditSpreadMomentum(), prices=empty)
