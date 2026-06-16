"""Integration test for short_strangle_monthly."""

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
from alphakit.strategies.options.short_strangle_monthly.strategy import (
    ShortStrangleMonthly,
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


def test_full_strangle_runs_end_to_end_with_two_short_legs() -> None:
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = ShortStrangleMonthly(chain_feed=chain_feed)
    assert get_discrete_legs(strategy) == strategy.discrete_legs
    assert len(strategy.discrete_legs) == 2

    legs = strategy.make_legs_prices(underlying)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying}).join(legs)
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "short_strangle_monthly"
    assert np.isfinite(result.metrics["sharpe"])

    # Pure-options trade: underlying weight 0.
    assert (result.weights[strategy.underlying_symbol] == 0.0).all()
    # Both legs trade.
    for leg_col in strategy.discrete_legs:
        leg_w = result.weights[leg_col].to_numpy()
        assert (leg_w == -1.0).any()
        assert (leg_w == 1.0).any()


def test_mode_2_underlying_only_is_degenerate_no_trade() -> None:
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = ShortStrangleMonthly(chain_feed=chain_feed)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying})
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert abs(result.metrics["final_equity"] - 100_000.0) < 1.0
