"""Integration test for gamma_scalping_daily.

Verifies the composition wrapper's identical-trade-behaviour
contract: backtest results from gamma_scalping_daily and
delta_hedged_straddle should match (up to floating-point noise)
on the same fixture.
"""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd
from alphakit.bridges import vectorbt_bridge
from alphakit.core.data import OptionChain
from alphakit.core.protocols import (
    BacktestResult,
    raise_chain_not_supported,
)
from alphakit.data.options.synthetic import SyntheticOptionsFeed
from alphakit.strategies.options.delta_hedged_straddle.strategy import (
    DeltaHedgedStraddle,
)
from alphakit.strategies.options.gamma_scalping_daily.strategy import GammaScalpingDaily


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


def test_full_gamma_scalping_runs_end_to_end() -> None:
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = GammaScalpingDaily(chain_feed=chain_feed)

    legs = strategy.make_legs_prices(underlying)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying}).join(legs)
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "gamma_scalping_daily"
    assert result.meta["paper_doi"] == "ISBN:978-0470181998"
    assert np.isfinite(result.metrics["sharpe"])


def test_gamma_scalping_matches_delta_hedged_straddle() -> None:
    """Composition-wrapper transparency: outer + inner produce
    identical equity curves on the same fixture."""
    underlying = _deterministic_underlying()
    feed_outer = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    feed_inner = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))

    outer = GammaScalpingDaily(chain_feed=feed_outer)
    inner = DeltaHedgedStraddle(chain_feed=feed_inner)

    legs_outer = outer.make_legs_prices(underlying)
    legs_inner = inner.make_legs_prices(underlying)
    pd.testing.assert_frame_equal(legs_outer, legs_inner)

    prices_outer = pd.DataFrame({outer.underlying_symbol: underlying}).join(legs_outer)
    prices_inner = pd.DataFrame({inner.underlying_symbol: underlying}).join(legs_inner)
    r_outer = vectorbt_bridge.run(strategy=outer, prices=prices_outer)
    r_inner = vectorbt_bridge.run(strategy=inner, prices=prices_inner)

    # Equity curves should match to within numerical precision —
    # the composition wrapper does NOT introduce any trade-side
    # divergence from the inner strategy.
    pd.testing.assert_series_equal(
        r_outer.equity_curve,
        r_inner.equity_curve,
        check_names=False,
    )
