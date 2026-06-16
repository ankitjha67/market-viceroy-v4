"""Integration tests for cash_secured_put_systematic.

End-to-end pipeline mirrors covered_call_systematic's integration
test, with put-leg construction (via :meth:`make_put_leg_prices`)
replacing call-leg.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import cast

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.data import OptionChain
from alphakit.core.protocols import (
    BacktestResult,
    get_discrete_legs,
    raise_chain_not_supported,
)
from alphakit.data.options.synthetic import SyntheticOptionsFeed
from alphakit.strategies.options.cash_secured_put_systematic.strategy import (
    CashSecuredPutSystematic,
)


class _FakeUnderlying:
    """Slicing fake feed (matches covered_call_systematic's test pattern)."""

    name = "fake-underlying"

    def __init__(self, prices: pd.Series) -> None:
        self._prices = prices

    def fetch(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        end_ts = pd.Timestamp(end)
        sliced = self._prices.loc[:end_ts]
        return pd.DataFrame({symbols[0]: sliced.copy()})

    def fetch_chain(self, underlying: str, as_of: datetime) -> OptionChain:
        raise_chain_not_supported(self.name)


def _deterministic_underlying(
    n: int = 800, end_date: date = date(2024, 12, 31), seed: int = 42
) -> pd.Series:
    rng = np.random.default_rng(seed)
    daily_log_returns = rng.standard_normal(n) * 0.013
    values = 100.0 * np.exp(np.cumsum(daily_log_returns))
    index = pd.date_range(end=pd.Timestamp(end_date), periods=n, freq="B")
    return pd.Series(values, index=index, name="SPY")


def _build_strategy_and_feed(
    underlying: pd.Series,
) -> tuple[CashSecuredPutSystematic, SyntheticOptionsFeed]:
    fake = _FakeUnderlying(underlying)
    chain_feed = SyntheticOptionsFeed(underlying_feed=fake)
    strategy = CashSecuredPutSystematic(
        underlying_symbol="SPY",
        otm_pct=0.05,
        chain_feed=chain_feed,
    )
    return strategy, chain_feed


# ---------------------------------------------------------------------------
# make_put_leg_prices contract
# ---------------------------------------------------------------------------
def test_make_put_leg_prices_returns_named_series() -> None:
    underlying = _deterministic_underlying()
    strategy, _ = _build_strategy_and_feed(underlying)
    leg = strategy.make_put_leg_prices(underlying)
    assert isinstance(leg, pd.Series)
    assert leg.name == strategy.put_leg_symbol
    assert leg.index.equals(underlying.index)
    assert (leg >= 0.0).all()


def test_make_put_leg_prices_writes_each_post_warmup_month() -> None:
    underlying = _deterministic_underlying()
    strategy, _ = _build_strategy_and_feed(underlying)
    leg = strategy.make_put_leg_prices(underlying)
    idx = cast(pd.DatetimeIndex, leg.index)
    monthly_max = leg.groupby(idx.to_period("M")).max()
    post_warmup = monthly_max.iloc[14:]
    assert (post_warmup > 0).all()


def test_make_put_leg_prices_rejects_non_series() -> None:
    strategy, _ = _build_strategy_and_feed(_deterministic_underlying())
    with pytest.raises(TypeError, match="Series"):
        strategy.make_put_leg_prices(pd.DataFrame())  # type: ignore[arg-type]


def test_make_put_leg_prices_rejects_non_datetime_index() -> None:
    strategy, _ = _build_strategy_and_feed(_deterministic_underlying())
    with pytest.raises(TypeError, match="DatetimeIndex"):
        strategy.make_put_leg_prices(pd.Series([100.0, 101.0]))


def test_make_put_leg_prices_handles_empty_input() -> None:
    strategy, _ = _build_strategy_and_feed(_deterministic_underlying())
    out = strategy.make_put_leg_prices(pd.Series([], dtype=float, index=pd.DatetimeIndex([])))
    assert out.empty
    assert out.name == strategy.put_leg_symbol


# ---------------------------------------------------------------------------
# Mode 1 — full CSP end-to-end
# ---------------------------------------------------------------------------
def test_full_csp_runs_through_vectorbt_bridge_with_discrete_legs() -> None:
    underlying = _deterministic_underlying()
    strategy, _ = _build_strategy_and_feed(underlying)
    assert get_discrete_legs(strategy) == (strategy.put_leg_symbol,)

    leg = strategy.make_put_leg_prices(underlying)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying, strategy.put_leg_symbol: leg})
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "cash_secured_put_systematic"
    assert np.isfinite(result.metrics["sharpe"])
    assert (result.weights[strategy.underlying_symbol] == 1.0).all()
    leg_w = result.weights[strategy.put_leg_symbol].to_numpy()
    assert (leg_w == -1.0).any()
    assert (leg_w == 1.0).any()


def test_mode_1_diverges_from_pure_buy_and_hold() -> None:
    """Mode 1 P&L diverges from Mode 2 buy-and-hold during in-position
    phase due to put-leg mark-to-market."""
    underlying = _deterministic_underlying()
    strategy, _ = _build_strategy_and_feed(underlying)
    leg = strategy.make_put_leg_prices(underlying)
    prices_1 = pd.DataFrame({strategy.underlying_symbol: underlying, strategy.put_leg_symbol: leg})
    prices_2 = pd.DataFrame({strategy.underlying_symbol: underlying})
    r1 = vectorbt_bridge.run(strategy=strategy, prices=prices_1)
    r2 = vectorbt_bridge.run(strategy=strategy, prices=prices_2)
    diff = (r1.equity_curve - r2.equity_curve).abs()
    assert float(diff.max()) > 4.0


# ---------------------------------------------------------------------------
# Mode 2 — buy-and-hold approximation
# ---------------------------------------------------------------------------
def test_buy_and_hold_mode_runs_through_vectorbt_bridge() -> None:
    underlying = _deterministic_underlying()
    strategy, _ = _build_strategy_and_feed(underlying)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying})
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "cash_secured_put_systematic"
    assert np.isfinite(result.metrics["sharpe"])


def test_full_pipeline_is_deterministic() -> None:
    underlying = _deterministic_underlying()
    sa, _ = _build_strategy_and_feed(underlying)
    sb, _ = _build_strategy_and_feed(underlying)
    pd.testing.assert_series_equal(
        sa.make_put_leg_prices(underlying),
        sb.make_put_leg_prices(underlying),
    )
