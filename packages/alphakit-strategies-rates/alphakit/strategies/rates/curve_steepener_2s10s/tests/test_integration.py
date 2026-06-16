"""Integration tests for curve_steepener_2s10s.

Mocks ``FREDAdapter.fetch`` to return synthetic ``DGS2`` and ``DGS10``
yield series, derives short-end and long-end bond-price proxies via
the duration approximation, runs the strategy through the vectorbt
bridge, and asserts the returned :class:`BacktestResult` is internally
consistent.

Network is never touched; FRED is mocked at the adapter-method level.
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
from alphakit.strategies.rates.curve_steepener_2s10s.strategy import CurveSteepener2s10s

_TWO_YEAR_DURATION = 1.95
_TEN_YEAR_DURATION = 8.0


def _synthetic_dgs2_dgs10(seed: int = 42, years: float = 6) -> pd.DataFrame:
    """Synthetic 2Y and 10Y yields with a slowly-moving 2s10s spread.

    Spread oscillates around 1.5%; both yields drift around their
    long-run means with correlated daily increments to produce realistic
    parallel-shift dominance.
    """
    rng = np.random.default_rng(seed)
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")

    parallel_increments = rng.normal(0.0, 0.04, size=n_days)
    spread_increments = rng.normal(0.0, 0.02, size=n_days)
    parallel = 3.0 + np.cumsum(parallel_increments) * 0.5
    spread = 1.5 + np.cumsum(spread_increments) * 0.5
    parallel = np.clip(parallel, 0.5, 7.0)
    spread = np.clip(spread, -0.5, 3.5)

    dgs10 = parallel + spread / 2.0
    dgs2 = parallel - spread / 2.0
    dgs2 = np.clip(dgs2, 0.05, None)
    return pd.DataFrame({"DGS2": dgs2, "DGS10": dgs10}, index=index)


def _yields_to_two_leg_prices(yields_pct: pd.DataFrame) -> pd.DataFrame:
    """Convert a 2-column yield DataFrame to a 2-column price proxy
    (short-end first, long-end second) via the duration approximation.
    """
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

    with patch.object(FREDAdapter, "fetch", return_value=fred_response) as mock_fetch:
        adapter = FREDAdapter()
        yields = adapter.fetch(
            symbols=["DGS2", "DGS10"],
            start=datetime(2018, 1, 1),
            end=datetime(2024, 1, 1),
        )
        assert mock_fetch.called

    prices = _yields_to_two_leg_prices(yields)
    strategy = CurveSteepener2s10s()
    result = vectorbt_bridge.run(
        strategy=strategy,
        prices=prices,
        initial_cash=100_000.0,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.meta["engine"] == "vectorbt"
    assert result.meta["strategy"] == "curve_steepener_2s10s"
    assert result.meta["paper_doi"] == "10.1257/0002828053828581"

    assert len(result.equity_curve) == len(prices)
    assert len(result.returns) == len(prices)
    assert result.weights.shape == prices.shape

    for key in ("sharpe", "sortino", "calmar", "max_drawdown", "final_equity"):
        assert key in result.metrics, f"missing metric: {key}"
        assert np.isfinite(result.metrics[key]), f"non-finite metric: {key}"

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
    pd.testing.assert_frame_equal(prices_a, prices_b)

    strategy = CurveSteepener2s10s()
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
        columns=["SHY_proxy", "TLT_proxy"],
        dtype=float,
    )
    with pytest.raises(ValueError, match="empty"):
        vectorbt_bridge.run(strategy=CurveSteepener2s10s(), prices=empty)
