"""Integration test for bxmp_overlay.

End-to-end through vectorbt_bridge with discrete_legs dispatch on
BOTH option legs (3-instrument book: underlying + call + put).
First multi-discrete-leg integration test in Session 2F.
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
from alphakit.strategies.options.bxmp_overlay.strategy import BXMPOverlay


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


def test_full_bxmp_runs_end_to_end_with_two_discrete_legs() -> None:
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = BXMPOverlay(chain_feed=chain_feed)

    # Two discrete legs declared.
    assert get_discrete_legs(strategy) == (strategy.call_leg_symbol, strategy.put_leg_symbol)

    leg_call = strategy.make_call_leg_prices(underlying)
    leg_put = strategy.make_put_leg_prices(underlying)
    prices = pd.DataFrame(
        {
            strategy.underlying_symbol: underlying,
            strategy.call_leg_symbol: leg_call,
            strategy.put_leg_symbol: leg_put,
        }
    )
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "bxmp_overlay"
    assert np.isfinite(result.metrics["sharpe"])

    # Both legs should have at least one write and one close event.
    for leg_col in (strategy.call_leg_symbol, strategy.put_leg_symbol):
        leg_w = result.weights[leg_col].to_numpy()
        assert (leg_w == -1.0).any(), f"expected ≥1 write on {leg_col}"
        assert (leg_w == 1.0).any(), f"expected ≥1 close on {leg_col}"


def test_bxmp_diverges_from_buy_and_hold() -> None:
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = BXMPOverlay(chain_feed=chain_feed)

    leg_call = strategy.make_call_leg_prices(underlying)
    leg_put = strategy.make_put_leg_prices(underlying)
    prices_1 = pd.DataFrame(
        {
            strategy.underlying_symbol: underlying,
            strategy.call_leg_symbol: leg_call,
            strategy.put_leg_symbol: leg_put,
        }
    )
    prices_2 = pd.DataFrame({strategy.underlying_symbol: underlying})
    r1 = vectorbt_bridge.run(strategy=strategy, prices=prices_1)
    r2 = vectorbt_bridge.run(strategy=strategy, prices=prices_2)
    diff = (r1.equity_curve - r2.equity_curve).abs()
    # Empirically larger than single-leg variants since BOTH legs
    # contribute mark-to-market divergence; threshold conservative.
    assert float(diff.max()) > 4.0


def test_bxmp_underlying_only_runs_in_mode_2_fallback() -> None:
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = BXMPOverlay(chain_feed=chain_feed)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying})
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert np.isfinite(result.metrics["sharpe"])
    assert (result.weights[strategy.underlying_symbol] == 1.0).all()
