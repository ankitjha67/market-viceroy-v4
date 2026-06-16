"""Integration test for put_skew_premium.

⚠ Substrate-caveat strategy — see strategy module docstring and
known_failures.md §1. The synthetic chain has flat IV, so the
put-skew premium is structurally zero. Integration tests verify
plumbing (legs trade, lifecycle correct) but NOT the strategy's
target P&L.
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
from alphakit.strategies.options.put_skew_premium.strategy import PutSkewPremium


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


def test_full_risk_reversal_runs_end_to_end() -> None:
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = PutSkewPremium(chain_feed=chain_feed)

    legs = strategy.make_legs_prices(underlying)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying}).join(legs)
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "put_skew_premium"
    assert np.isfinite(result.metrics["sharpe"])
    assert (result.weights[strategy.underlying_symbol] == 0.0).all()


def test_substrate_caveat_both_legs_priced_with_same_sigma() -> None:
    """Substrate-caveat smoke test: on the flat-IV synthetic chain,
    both legs are priced with the SAME sigma per cycle. This means
    the strategy's target premium (skew differential) is
    structurally zero on this substrate.

    Real-feed equivalent (Phase 3): put_iv > call_iv consistently
    by 5-15 %, generating the put-skew premium this strategy
    targets. The synthetic backtest is uninformative for that
    premium.

    The test verifies that BOTH legs see at least one in-position
    bar (lifecycle plumbing works) — does NOT assert any
    quantitative ratio because spot drift through cycles produces
    a wide ratio range under flat IV.
    """
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = PutSkewPremium(chain_feed=chain_feed)
    legs = strategy.make_legs_prices(underlying)
    assert (legs[strategy.put_leg_symbol] > 1e-3).any()
    assert (legs[strategy.call_leg_symbol] > 1e-3).any()


def test_mode_2_underlying_only_is_degenerate_no_trade() -> None:
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = PutSkewPremium(chain_feed=chain_feed)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying})
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert abs(result.metrics["final_equity"] - 100_000.0) < 1.0
