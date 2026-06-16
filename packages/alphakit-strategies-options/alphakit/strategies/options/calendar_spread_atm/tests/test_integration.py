"""Integration test for calendar_spread_atm."""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd
from alphakit.bridges import vectorbt_bridge
from alphakit.core.data import OptionChain
from alphakit.core.protocols import (
    BacktestResult,
    get_discrete_legs,
    raise_chain_not_supported,
)
from alphakit.data.options.synthetic import SyntheticOptionsFeed
from alphakit.strategies.options.calendar_spread_atm.strategy import CalendarSpreadATM


class _FakeUnderlying:
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
        return pd.DataFrame({symbols[0]: self._prices.loc[:end_ts].copy()})

    def fetch_chain(self, underlying: str, as_of: datetime) -> OptionChain:
        raise_chain_not_supported(self.name)


def _deterministic_underlying() -> pd.Series:
    rng = np.random.default_rng(42)
    n = 800
    daily_log_returns = rng.standard_normal(n) * 0.013
    values = 100.0 * np.exp(np.cumsum(daily_log_returns))
    index = pd.date_range(end=pd.Timestamp(date(2024, 12, 31)), periods=n, freq="B")
    return pd.Series(values, index=index, name="SPY")


def test_full_calendar_spread_runs_end_to_end() -> None:
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = CalendarSpreadATM(chain_feed=chain_feed)
    assert get_discrete_legs(strategy) == strategy.discrete_legs

    legs = strategy.make_legs_prices(underlying)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying}).join(legs)
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "calendar_spread_atm"
    assert np.isfinite(result.metrics["sharpe"])

    assert (result.weights[strategy.underlying_symbol] == 0.0).all()
    # Front leg: short writes / closes.
    front_w = result.weights[strategy.front_leg_symbol].to_numpy()
    assert (front_w == -1.0).any()
    assert (front_w == 1.0).any()
    # Back leg: long writes / closes.
    back_w = result.weights[strategy.back_leg_symbol].to_numpy()
    assert (back_w == 1.0).any()
    assert (back_w == -1.0).any()


def test_back_leg_premium_exceeds_front_leg_premium_at_write() -> None:
    """At write, the back-month call has more time value than the
    front-month → back premium > front premium for the same K."""
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = CalendarSpreadATM(chain_feed=chain_feed)
    legs = strategy.make_legs_prices(underlying)

    # Find write events on the front leg (zero-to-positive).
    front = legs[strategy.front_leg_symbol].to_numpy()
    back = legs[strategy.back_leg_symbol].to_numpy()
    is_open = front > 1e-3
    prev_open = np.concatenate(([False], is_open[:-1]))
    write_mask = is_open & ~prev_open

    write_indices = np.where(write_mask)[0]
    assert len(write_indices) > 0
    # On every write date, back >= front (back has more time value).
    assert (back[write_indices] >= front[write_indices]).all()


def test_mode_2_underlying_only_is_degenerate_no_trade() -> None:
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = CalendarSpreadATM(chain_feed=chain_feed)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying})
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert abs(result.metrics["final_equity"] - 100_000.0) < 1.0
