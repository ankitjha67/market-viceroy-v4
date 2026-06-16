"""Integration tests for bond_tsmom_12_1.

Mocks ``FREDAdapter.fetch`` to return a deterministic synthetic 10Y
yield series, derives a price-like proxy via the duration approximation
documented in ``paper.md``, runs the strategy through the vectorbt
bridge, and asserts that the returned :class:`BacktestResult` is
internally consistent.

We deliberately **do not** assert specific Sharpe values against the
published paper — synthetic data cannot reproduce real markets. The
goal is to prove the bridge plumbing works on the rates feed, not to
validate the paper.

Network is never touched; FRED is mocked at the adapter-method level.
"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.data.rates.fred_adapter import FREDAdapter
from alphakit.strategies.rates.bond_tsmom_12_1.strategy import BondTSMOM12m1m

# Modified duration of the on-the-run 10Y treasury, used to convert
# yield changes to bond returns. Approximate; see ``paper.md``.
_TEN_YEAR_MODIFIED_DURATION = 8.0


def _synthetic_dgs10_yields(seed: int = 42, years: float = 6) -> pd.Series:
    """Deterministic synthetic 10Y yield series, in percent.

    Mean-reverting around 3.0% with realistic monthly increments —
    enough range to exercise the momentum signal without producing
    pathological zero-or-negative yields.
    """
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    daily_increments = rng.normal(0.0, 0.04, size=n_days)
    yields = 3.0 + np.cumsum(daily_increments) * 0.5
    yields = np.clip(yields, 0.5, 7.0)
    return pd.Series(yields, index=index, name="DGS10")


def _yields_to_bond_prices(yields_pct: pd.Series) -> pd.DataFrame:
    """Convert a yield series (in percent) to a price-like proxy.

    Uses the duration approximation ``return ≈ -duration * Δy`` (see
    ``paper.md``). Drops the carry and convexity terms — acceptable
    for sign-of-cumulative-return signal generation.
    """
    yields_decimal = yields_pct / 100.0
    daily_returns = -_TEN_YEAR_MODIFIED_DURATION * yields_decimal.diff().fillna(0.0)
    prices = 100.0 * np.exp(daily_returns.cumsum())
    return cast(pd.DataFrame, prices.to_frame(name="TLT_proxy"))


@pytest.mark.integration
def test_backtest_runs_end_to_end_with_mocked_fred() -> None:
    """Mock FRED, derive bond proxy, run strategy via vectorbt bridge."""
    synthetic_yields = _synthetic_dgs10_yields(seed=42, years=6)
    fred_response = pd.DataFrame({"DGS10": synthetic_yields})

    with patch.object(FREDAdapter, "fetch", return_value=fred_response) as mock_fetch:
        adapter = FREDAdapter()
        yields = adapter.fetch(
            symbols=["DGS10"],
            start=datetime(2018, 1, 1),
            end=datetime(2024, 1, 1),
        )
        assert mock_fetch.called

    prices = _yields_to_bond_prices(yields["DGS10"])
    strategy = BondTSMOM12m1m()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "bond_tsmom_12_1"
    assert result.meta["paper_doi"] == "10.1111/jofi.12021"

    assert len(result.equity_curve) == len(prices)
    assert len(result.returns) == len(prices)
    assert result.weights.shape == prices.shape

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics, f"missing metric: {key}"
        assert np.isfinite(result.metrics[key]), f"non-finite metric: {key}"

    assert result.metrics["max_drawdown"] <= 0.0


@pytest.mark.integration
def test_backtest_is_deterministic_with_mocked_fred() -> None:
    """Same mocked feed → identical backtest result."""
    synthetic_yields = _synthetic_dgs10_yields(seed=123, years=5)
    fred_response = pd.DataFrame({"DGS10": synthetic_yields})

    with patch.object(FREDAdapter, "fetch", return_value=fred_response):
        adapter = FREDAdapter()
        yields_a = adapter.fetch(
            symbols=["DGS10"], start=datetime(2018, 1, 1), end=datetime(2023, 1, 1)
        )
        yields_b = adapter.fetch(
            symbols=["DGS10"], start=datetime(2018, 1, 1), end=datetime(2023, 1, 1)
        )

    prices_a = _yields_to_bond_prices(yields_a["DGS10"])
    prices_b = _yields_to_bond_prices(yields_b["DGS10"])
    pd.testing.assert_frame_equal(prices_a, prices_b)

    strategy = BondTSMOM12m1m()
    result_a = vectorbt_bridge.run(strategy=strategy, prices=prices_a)
    result_b = vectorbt_bridge.run(strategy=strategy, prices=prices_b)

    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    pd.testing.assert_frame_equal(result_a.weights, result_b.weights)
    for key, value in result_a.metrics.items():
        assert result_b.metrics[key] == pytest.approx(value)


@pytest.mark.integration
def test_backtest_rejects_empty_prices() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["TLT_proxy"],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=BondTSMOM12m1m(), prices=empty)
