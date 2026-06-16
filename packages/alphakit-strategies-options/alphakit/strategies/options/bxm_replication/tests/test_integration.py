"""Integration test for bxm_replication.

End-to-end through vectorbt_bridge with discrete_legs dispatch on
the synthetic chain. Mirrors covered_call_systematic's integration
test, swapping in BXMReplication (otm_pct=0.0 fixed).
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
from alphakit.strategies.options.bxm_replication.strategy import BXMReplication


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


def test_full_bxm_runs_through_vectorbt_bridge_with_discrete_legs() -> None:
    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = BXMReplication(chain_feed=chain_feed)
    assert get_discrete_legs(strategy) == (strategy.call_leg_symbol,)

    leg = strategy.make_call_leg_prices(underlying)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying, strategy.call_leg_symbol: leg})
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "bxm_replication"
    assert result.meta["paper_doi"] == "10.3905/jod.2002.319188"
    assert np.isfinite(result.metrics["sharpe"])
    assert (result.weights[strategy.underlying_symbol] == 1.0).all()
    leg_w = result.weights[strategy.call_leg_symbol].to_numpy()
    assert (leg_w == -1.0).any()
    assert (leg_w == 1.0).any()


def test_bxm_diverges_from_covered_call_2pct_otm() -> None:
    """Same trade-mechanic family but different strikes: BXM (ATM)
    and 2 % OTM should produce different premium magnitudes.

    The synthetic chain's 5 %-spaced grid means both strategies
    end up writing at strikes that differ by exactly one grid
    multiplier (1.00 vs 1.05); the ATM call has higher premium per
    cycle. Equity curves diverge.
    """
    from alphakit.strategies.options.covered_call_systematic.strategy import (
        CoveredCallSystematic,
    )

    underlying = _deterministic_underlying()
    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))

    bxm = BXMReplication(chain_feed=chain_feed)
    cc2 = CoveredCallSystematic(otm_pct=0.02, chain_feed=chain_feed)

    leg_bxm = bxm.make_call_leg_prices(underlying)
    leg_cc2 = cc2.make_call_leg_prices(underlying)

    # ATM premium > OTM premium at every in-position bar (BS-monotone in K).
    in_position_bxm = leg_bxm > 1e-3
    in_position_cc2 = leg_cc2 > 1e-3
    overlap = in_position_bxm & in_position_cc2
    assert overlap.any(), "expected at least one overlapping in-position bar"
    assert (leg_bxm[overlap] > leg_cc2[overlap]).all(), (
        "ATM premium must dominate OTM premium where both positions are open"
    )
