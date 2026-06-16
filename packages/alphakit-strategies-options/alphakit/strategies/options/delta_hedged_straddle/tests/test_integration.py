"""Integration test for delta_hedged_straddle."""

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
from alphakit.strategies.options.delta_hedged_straddle.strategy import (
    DeltaHedgedStraddle,
)


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


def test_full_delta_hedged_straddle_runs_end_to_end() -> None:
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = DeltaHedgedStraddle(chain_feed=chain_feed)
    assert get_discrete_legs(strategy) == strategy.discrete_legs

    legs = strategy.make_legs_prices(underlying)
    assert len(strategy._cycles) > 0  # state populated

    prices = pd.DataFrame({strategy.underlying_symbol: underlying}).join(legs)
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "delta_hedged_straddle"
    assert np.isfinite(result.metrics["sharpe"])

    # Long-leg trades: +1 at writes, -1 at closes.
    for leg_col in strategy.discrete_legs:
        leg_w = result.weights[leg_col].to_numpy()
        assert (leg_w == 1.0).any(), f"expected ≥1 BUY (write) on {leg_col}"
        assert (leg_w == -1.0).any(), f"expected ≥1 SELL (close) on {leg_col}"


def test_underlying_hedge_weight_is_time_varying_when_in_position() -> None:
    """Daily delta hedge produces a time-varying underlying weight."""
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = DeltaHedgedStraddle(chain_feed=chain_feed)
    legs = strategy.make_legs_prices(underlying)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying}).join(legs)
    weights = strategy.generate_signals(prices)
    underlying_w = weights[strategy.underlying_symbol]
    # During in-position bars the hedge weight is non-zero (delta drift).
    in_position_count = (underlying_w != 0.0).sum()
    assert in_position_count > 0, "expected non-zero hedge weight during in-position bars"
    # The hedge weight is bounded (|delta| ≤ 2 for a straddle, so |weight| ≤ 2).
    assert (underlying_w.abs() <= 2.0).all()


def test_mode_2_underlying_only_is_degenerate_no_trade() -> None:
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = DeltaHedgedStraddle(chain_feed=chain_feed)
    # Note: NOT calling make_legs_prices — cycles list stays empty.
    prices = pd.DataFrame({strategy.underlying_symbol: underlying})
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert abs(result.metrics["final_equity"] - 100_000.0) < 1.0
