"""Unit tests for delta_hedged_straddle."""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest
from alphakit.core.data import OptionChain
from alphakit.core.protocols import StrategyProtocol, get_discrete_legs, raise_chain_not_supported
from alphakit.data.options.synthetic import SyntheticOptionsFeed
from alphakit.strategies.options.delta_hedged_straddle.strategy import (
    DeltaHedgedStraddle,
    _detect_lifecycle_events,
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


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(DeltaHedgedStraddle(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = DeltaHedgedStraddle()
    assert s.name == "delta_hedged_straddle"
    assert s.family == "options"
    assert s.paper_doi == "10.1093/rfs/hhn038"  # Carr-Wu 2009
    assert s.rebalance_frequency == "daily"


def test_default_legs_use_atm_straddle_naming() -> None:
    s = DeltaHedgedStraddle()
    assert s.call_leg_symbol == "SPY_CALL_ATM_STRADDLE_M1"
    assert s.put_leg_symbol == "SPY_PUT_ATM_STRADDLE_M1"


def test_discrete_legs_includes_both_long_legs() -> None:
    s = DeltaHedgedStraddle()
    assert s.discrete_legs == (s.call_leg_symbol, s.put_leg_symbol)
    assert get_discrete_legs(s) == s.discrete_legs


def test_constructor_rejects_empty_underlying() -> None:
    with pytest.raises(ValueError, match="underlying_symbol"):
        DeltaHedgedStraddle(underlying_symbol="")


def test_generate_signals_emits_zero_underlying_when_no_cycles_state() -> None:
    """Without prior make_legs_prices → cycles list is empty → no
    delta hedge → underlying weight 0."""
    idx = pd.date_range("2024-01-02", periods=10, freq="B")
    s = DeltaHedgedStraddle()
    weights = s.generate_signals(pd.DataFrame({"SPY": np.full(10, 100.0)}, index=idx))
    assert (weights["SPY"] == 0.0).all()


def test_generate_signals_long_legs_emit_plus_at_write_minus_at_close() -> None:
    """Long straddle: +1 at write (BUY), -1 at close (SELL).

    Opposite sign convention to short-vol siblings (which sell at
    write / buy at close).
    """
    s = DeltaHedgedStraddle()
    idx = pd.date_range("2024-01-02", periods=11, freq="B")
    leg = [1e-6, 5.0, 4.0, 3.0, 2.0, 1.0, 0.5, 1e-6, 1e-6, 1e-6, 1e-6]
    prices = pd.DataFrame(
        {
            s.underlying_symbol: np.full(11, 100.0),
            s.call_leg_symbol: leg,
            s.put_leg_symbol: leg,
        },
        index=idx,
    )
    weights = s.generate_signals(prices)
    expected = np.zeros(11, dtype=float)
    expected[1] = 1.0  # BUY at write (long)
    expected[6] = -1.0  # SELL at close
    np.testing.assert_array_equal(weights[s.call_leg_symbol].to_numpy(), expected)
    np.testing.assert_array_equal(weights[s.put_leg_symbol].to_numpy(), expected)


def test_lifecycle_helper_matches_short_vol_strategies() -> None:
    """The lifecycle-detection helper is identical across all
    discrete-leg strategies in the family."""
    leg = np.array([1e-6, 5.0, 4.0, 3.0, 1e-6, 1e-6])
    write_mask, close_mask = _detect_lifecycle_events(leg)
    assert write_mask[1]
    assert close_mask[3]
    assert not write_mask[3]
    assert not close_mask[1]


def test_truncated_window_emits_trailing_hedge_weights() -> None:
    """Window ending mid-cycle still produces non-zero hedge weights
    on the underlying in the trailing bars.

    Regression test for Codex P1 finding on PR #16: cycles list was
    only appended inside the close-at-expiry branch, so truncated
    windows emitted zero hedge weights on the underlying for trailing
    bars while the option-leg lifecycle detection correctly fired
    (long straddle held unhedged → directional P&L bias).
    """
    rng = np.random.default_rng(7)
    # Build ample history (the synthetic feed needs ≥ 252 trailing
    # bars to compute realized vol) ending on a date that falls just
    # *after* a first-of-month write but well before the next expiry
    # — i.e., the window ends mid-cycle.
    n = 500
    daily_log_returns = rng.standard_normal(n) * 0.013
    values = 100.0 * np.exp(np.cumsum(daily_log_returns))
    index = pd.date_range(end=pd.Timestamp(date(2024, 8, 5)), periods=n, freq="B")
    underlying = pd.Series(values, index=index, name="SPY")

    chain_feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(underlying))
    strategy = DeltaHedgedStraddle(chain_feed=chain_feed)
    legs = strategy.make_legs_prices(underlying)

    # The trailing cycle must extend coverage to the final bar.
    # Pre-fix: the open trailing cycle was dropped → no cycle had
    # close_idx == n - 1 → no hedge weight on trailing bars.
    assert len(strategy._cycles) >= 1
    assert any(c.close_idx == n - 1 for c in strategy._cycles)

    prices = pd.DataFrame({strategy.underlying_symbol: underlying}).join(legs)
    weights = strategy.generate_signals(prices)
    # Trailing bars carry non-zero hedge weight on the underlying.
    # Pre-fix: this sum was 0.0 because no cycle covered the tail.
    assert weights[strategy.underlying_symbol].iloc[-10:].abs().sum() > 0
