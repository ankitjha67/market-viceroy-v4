"""Integration test for iron_condor_monthly.

End-to-end through vectorbt_bridge with 4-leg discrete dispatch
(first 4-discrete-leg integration test in Session 2F).
"""

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
from alphakit.strategies.options.iron_condor_monthly.strategy import IronCondorMonthly


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


def test_full_iron_condor_runs_end_to_end_with_four_discrete_legs() -> None:
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = IronCondorMonthly(chain_feed=chain_feed)
    assert get_discrete_legs(strategy) == strategy.discrete_legs
    assert len(strategy.discrete_legs) == 4

    legs = strategy.make_legs_prices(underlying)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying}).join(legs)
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "iron_condor_monthly"
    assert np.isfinite(result.metrics["sharpe"])

    # Underlying weight is 0 throughout (pure-options trade).
    assert (result.weights[strategy.underlying_symbol] == 0.0).all()

    # Each leg has at least one write and one close event.
    for leg_col in strategy.discrete_legs:
        leg_w = result.weights[leg_col].to_numpy()
        assert (np.abs(leg_w) == 1.0).any(), f"expected ≥1 trade on {leg_col}"


def test_iron_condor_short_legs_write_negative_long_legs_write_positive() -> None:
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = IronCondorMonthly(chain_feed=chain_feed)
    legs = strategy.make_legs_prices(underlying)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying}).join(legs)
    weights = strategy.generate_signals(prices)

    # Short legs: at least one bar with weight = -1 (write), at least one with +1 (close).
    for short_leg in (strategy.short_put_leg_symbol, strategy.short_call_leg_symbol):
        w = weights[short_leg].to_numpy()
        assert (w == -1.0).any()
        assert (w == 1.0).any()
    # Long legs: opposite signs (buy at write = +1; sell at close = -1).
    for long_leg in (strategy.long_put_leg_symbol, strategy.long_call_leg_symbol):
        w = weights[long_leg].to_numpy()
        assert (w == 1.0).any()
        assert (w == -1.0).any()


def test_mode_2_underlying_only_is_degenerate_no_trade() -> None:
    """Iron condor needs all 4 legs; underlying-only Mode 2 is a no-trade case."""
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = IronCondorMonthly(chain_feed=chain_feed)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying})
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    # All-zero weights → no trade → final equity == initial cash.
    assert abs(result.metrics["final_equity"] - 100_000.0) < 1.0
