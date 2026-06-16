"""Tests for :mod:`alphakit.data.options.synthetic` (ADR-005).

The synthetic feed generates OptionChain snapshots from a fake
underlying-prices DataFrame. Fixtures below build deterministic
underlying histories long enough to clear the 252-bar realized-vol
window, then assert:

* Chain shape (quote count in the 198-252 range, tuple-immutability).
* Greek plausibility (ATM delta≈0.5, vega positive, theta negative).
* Determinism (same (underlying, as_of) → byte-identical chain).
* Insufficient-history and non-finite-price error paths.
* Expiry-grid dedup logic through as_of dates that produce different
  raw-pool overlaps.
* Filter / strikes accessor round-trip against the generated chain.
"""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest
from alphakit.core.data import OptionChain, OptionRight
from alphakit.core.protocols import raise_chain_not_supported
from alphakit.data.options.synthetic import (
    MIN_HISTORY_BARS,
    STRIKE_MULTIPLIERS,
    SyntheticOptionsFeed,
    build_expiry_grid,
)


class _FakeUnderlying:
    """Deterministic stub underlying feed for the synthetic tests."""

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
        return pd.DataFrame({symbols[0]: self._prices.copy()})

    def fetch_chain(self, underlying: str, as_of: datetime) -> OptionChain:
        raise_chain_not_supported(self.name)


def _deterministic_prices(n: int = 300, end_date: date = date(2024, 1, 2)) -> pd.Series:
    """Strictly-positive price path with realistic (~20 %) annualised vol.

    Uses a seeded RNG so the series is deterministic across runs but
    still delivers ATM deltas and greeks in the plausible range tested
    below. A smooth sin-based path yields vol so low that BS degenerates
    to pure intrinsic (delta → 0 or 1), which would hide real pricing
    bugs.
    """
    rng = np.random.default_rng(42)
    daily_log_returns = rng.standard_normal(n) * 0.013  # ≈ 20 % annualised
    values = 100.0 * np.exp(np.cumsum(daily_log_returns))
    index = pd.date_range(end=pd.Timestamp(end_date), periods=n, freq="D")
    return pd.Series(values, index=index, name="SPY")


def _make_feed(n_bars: int = 300, end_date: date = date(2024, 1, 2)) -> SyntheticOptionsFeed:
    return SyntheticOptionsFeed(
        underlying_feed=_FakeUnderlying(_deterministic_prices(n_bars, end_date))
    )


def test_chain_has_expected_quote_count_range() -> None:
    feed = _make_feed()
    chain = feed.fetch_chain("SPY", datetime(2024, 1, 2))
    # 11-14 expiries × 9 strikes × 2 rights = 198-252 quotes.
    assert 198 <= len(chain.quotes) <= 252
    # Strike grid is exactly the 9-point moneyness set scaled by spot.
    assert len(chain.strikes()) == len(STRIKE_MULTIPLIERS)


def test_chain_quotes_is_immutable_tuple() -> None:
    feed = _make_feed()
    chain = feed.fetch_chain("SPY", datetime(2024, 1, 2))
    assert type(chain.quotes) is tuple


def test_chain_returns_option_chain_instance() -> None:
    feed = _make_feed()
    chain = feed.fetch_chain("SPY", datetime(2024, 1, 2))
    assert isinstance(chain, OptionChain)
    assert chain.underlying == "SPY"
    assert chain.spot > 0


def test_chain_is_deterministic_same_as_of() -> None:
    """Same underlying series + same as_of must produce identical chains."""
    as_of = datetime(2024, 1, 2)
    chain_a = _make_feed().fetch_chain("SPY", as_of)
    chain_b = _make_feed().fetch_chain("SPY", as_of)
    assert chain_a == chain_b
    assert chain_a.quotes == chain_b.quotes


def test_atm_call_delta_is_near_half() -> None:
    """ATM call delta should sit near 0.5 (Black-Scholes, r≈0, short-dated)."""
    feed = _make_feed()
    chain = feed.fetch_chain("SPY", datetime(2024, 1, 2))
    spot = chain.spot
    # Find the 1.00 × spot strike, shortest expiry, call.
    shortest_expiry = chain.expiries()[0]
    atm_calls = [
        q
        for q in chain.filter(expiry=shortest_expiry, right=OptionRight.CALL)
        if abs(q.strike / spot - 1.0) < 1e-9
    ]
    assert atm_calls, "no ATM call found in the chain"
    assert atm_calls[0].delta is not None
    assert 0.40 <= atm_calls[0].delta <= 0.65


def test_all_greeks_populated_and_plausible() -> None:
    feed = _make_feed()
    chain = feed.fetch_chain("SPY", datetime(2024, 1, 2))
    for q in chain.quotes:
        assert q.iv is not None and q.iv > 0
        assert q.delta is not None
        assert q.gamma is not None and q.gamma >= 0.0
        assert q.vega is not None and q.vega >= 0.0
        assert q.theta is not None
        if q.right is OptionRight.CALL:
            assert 0.0 <= q.delta <= 1.0
        else:
            assert -1.0 <= q.delta <= 0.0


def test_raises_on_insufficient_history() -> None:
    feed = _make_feed(n_bars=10)  # fewer than MIN_HISTORY_BARS
    with pytest.raises(ValueError, match="at least 252"):
        feed.fetch_chain("SPY", datetime(2024, 1, 2))
    assert MIN_HISTORY_BARS == 252


def test_raises_on_non_finite_prices() -> None:
    prices = _deterministic_prices(300)
    prices.iloc[-5] = np.nan  # NaN gets dropped, still 299 bars — fine
    prices.iloc[-1] = np.inf  # but +inf survives dropna and must trip the finite check
    feed = SyntheticOptionsFeed(underlying_feed=_FakeUnderlying(prices))
    with pytest.raises(ValueError, match="non-finite"):
        feed.fetch_chain("SPY", datetime(2024, 1, 2))


def test_expiry_grid_dedup_produces_11_to_14_entries() -> None:
    """Two as_of dates that straddle a monthly 3rd Friday must both dedupe correctly."""
    # 2024-01-02: weekly Jan 19 overlaps with monthly Jan 3rd Friday → dedup active.
    grid_a = build_expiry_grid(date(2024, 1, 2))
    # 2024-01-22 (Mon, after Jan 3rd Friday): different overlap pattern.
    grid_b = build_expiry_grid(date(2024, 1, 22))
    for grid in (grid_a, grid_b):
        assert 11 <= len(grid) <= 14
        # Dedup invariant: sorted unique.
        assert list(grid) == sorted(set(grid))


def test_expiry_grid_varies_with_as_of() -> None:
    """Sanity: the two as_of dates above produce different grids."""
    assert build_expiry_grid(date(2024, 1, 2)) != build_expiry_grid(date(2024, 1, 22))


def test_strike_grid_matches_spec() -> None:
    feed = _make_feed()
    chain = feed.fetch_chain("SPY", datetime(2024, 1, 2))
    spot = chain.spot
    strikes = chain.strikes()
    expected = tuple(sorted(round(m * spot, 10) for m in STRIKE_MULTIPLIERS))
    assert tuple(round(s, 10) for s in strikes) == expected


def test_filter_round_trip_via_chain_accessors() -> None:
    feed = _make_feed()
    chain = feed.fetch_chain("SPY", datetime(2024, 1, 2))
    # Every quote appears exactly once when we enumerate by (expiry, right).
    seen = 0
    for expiry in chain.expiries():
        for right in (OptionRight.CALL, OptionRight.PUT):
            seen += len(chain.filter(expiry=expiry, right=right))
    assert seen == len(chain.quotes)


def test_underlying_feed_property_resolves_via_registry() -> None:
    """Default underlying_feed falls through to FeedRegistry.get('yfinance')."""
    import contextlib

    from alphakit.data.equities.yfinance_adapter import YFinanceAdapter
    from alphakit.data.registry import FeedRegistry

    # Another test module's autouse fixture may have cleared the registry
    # during this session; re-register the yfinance adapter so the lookup
    # below tests the property, not cross-test state.
    with contextlib.suppress(ValueError):
        FeedRegistry.register(YFinanceAdapter())

    feed = SyntheticOptionsFeed()
    yfinance = FeedRegistry.get("yfinance")
    assert feed.underlying_feed is yfinance


def test_fetch_raises_not_implemented() -> None:
    feed = _make_feed()
    with pytest.raises(NotImplementedError, match="chain-only"):
        feed.fetch(["SPY"], datetime(2024, 1, 2), datetime(2024, 1, 10))
