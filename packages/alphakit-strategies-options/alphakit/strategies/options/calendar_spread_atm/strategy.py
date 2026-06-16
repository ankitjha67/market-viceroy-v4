"""ATM calendar spread: short front-month + long back-month call.

Foundational paper
------------------
Goyal, A. & Saretto, A. (2009). *Cross-Section of Option Returns
and Volatility*. Journal of Finance, 64(4), 1857-1898.
https://doi.org/10.1111/j.1540-6261.2009.01493.x

Goyal-Saretto study cross-sectional option returns conditional on
the *implied-vs-realized-vol gap* and the *term structure of
implied volatility*. Their headline finding: options with high
realized-minus-implied vol gap predict positive long-vol returns.
The calendar spread isolates a specific term-structure exposure:
short front-month + long back-month captures *expected
term-structure normalisation* — when the front-month IV is
elevated relative to back-month (e.g., near-event vol bump), the
spread profits as front-month theta decays faster than back-month.

Strategy structure
------------------
For each first trading day of a calendar month:

1. **Short front-month ATM call.** Strike = ATM at write. Expiry
   = first chain expiry > 25 days from write (~30-day DTE).
2. **Long back-month ATM call.** Same ATM strike, longer expiry
   = first chain expiry > 55 days from write (~60-day DTE).
3. **Close.** Both legs close at front-month expiry. Front
   closes at intrinsic; back closes at its remaining time value
   (~30 days to its own expiry).
4. **Position sizing.** -1 contract front + +1 contract back
   per cycle. Net premium paid = back_premium - front_premium
   (typically positive — the back is more expensive). Profit
   = net_premium_received_at_close - net_premium_paid_at_write.

Term-structure dependence on the synthetic chain
------------------------------------------------
The synthetic-options adapter (ADR-005) maps DTE buckets to
realized-vol windows: <45 DTE → 30-day RV, <120 → 60-day RV,
≥120 → 90-day RV. The front-month (~30 DTE) and back-month
(~60 DTE) calls are typically priced with *different sigmas*
(rv30 vs rv60), giving a meaningful synthetic term structure.

In practice rv30 and rv60 on a stable underlying are similar
(within 1-3 vol points), so the synthetic-chain term structure
is mild. Real markets have richer term-structure variation
(seasonal, event-driven). The synthetic substrate captures the
*direction* of the trade (term-structure normalisation harvest)
but not its *full magnitude*.

Differentiation from siblings
-----------------------------
* vs ``covered_call_systematic`` (Commit 2): Single-leg vs 2-leg
  term-structure spread. Different exposures.
* vs ``bxm_replication`` (Commit 4): Single ATM call write vs
  short front + long back. Calendar spread hedges the call write
  with a longer-dated long position.
* vs ``delta_hedged_straddle`` (Commit 9): Both target volatility
  exposure but differently — calendar spread is term-structure
  arbitrage, delta-hedged-straddle is daily-vol harvest.
* Cluster ρ ≈ 0.30-0.55 with most siblings — calendar spread has
  distinct exposure (term structure) not present in single-expiry
  strategies.

Bridge integration: 2 discrete legs
-----------------------------------
Strategy declares ``discrete_legs = (front_leg_symbol,
back_leg_symbol)``; bridge applies ``Amount`` semantics to both.
Underlying weight 0 (pure-options trade). Standard pattern.

Documented in ``known_failures.md``.
"""

from __future__ import annotations

import contextlib
from datetime import date, datetime
from typing import cast

import numpy as np
import pandas as pd
from alphakit.core.data import OptionChain, OptionRight
from alphakit.core.protocols import DataFeedProtocol
from alphakit.data.options import bs
from alphakit.data.registry import FeedRegistry

_DEFAULT_RISK_FREE_RATE: float = 0.045
_DAYS_PER_YEAR: float = 365.0
_LEG_FLAT_FLOOR: float = 1e-6
_LEG_PRICE_EPSILON: float = 1e-3
_FRONT_MIN_DTE_DAYS: int = 25
_BACK_MIN_DTE_DAYS: int = 55  # at least 30 days past the front-month expiry


def _to_date(d: date | datetime | pd.Timestamp) -> date:
    if isinstance(d, pd.Timestamp):
        return d.date()
    if isinstance(d, datetime):
        return d.date()
    return d


def _is_first_trading_day_of_month(idx: pd.DatetimeIndex) -> np.ndarray:
    months = idx.to_period("M")
    is_first = np.zeros(len(idx), dtype=bool)
    is_first[0] = True
    is_first[1:] = months[1:] != months[:-1]
    return is_first


class CalendarSpreadATM:
    """ATM calendar spread: short front + long back ATM call.

    Parameters
    ----------
    underlying_symbol
        Column name for the underlying. Defaults to ``"SPY"``.
        Pure-options trade — no underlying weight emitted.
    chain_feed
        Optional explicit feed object.
    """

    name: str = "calendar_spread_atm"
    family: str = "options"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1111/j.1540-6261.2009.01493.x"  # Goyal-Saretto 2009
    rebalance_frequency: str = "monthly"

    discrete_legs: tuple[str, ...]

    def __init__(
        self,
        *,
        underlying_symbol: str = "SPY",
        chain_feed: DataFeedProtocol | None = None,
    ) -> None:
        if not underlying_symbol:
            raise ValueError("underlying_symbol must be a non-empty string")
        self.underlying_symbol = underlying_symbol
        self._chain_feed = chain_feed
        self.discrete_legs = (self.front_leg_symbol, self.back_leg_symbol)

    @property
    def chain_feed(self) -> DataFeedProtocol:
        if self._chain_feed is not None:
            return self._chain_feed
        return FeedRegistry.get("synthetic-options")

    @property
    def front_leg_symbol(self) -> str:
        """Short front-month ATM call leg column."""
        return f"{self.underlying_symbol}_CALL_ATM_FRONT_M1"

    @property
    def back_leg_symbol(self) -> str:
        """Long back-month ATM call leg column."""
        return f"{self.underlying_symbol}_CALL_ATM_BACK_M2"

    def make_legs_prices(
        self,
        underlying_prices: pd.Series,
        *,
        chain_feed: DataFeedProtocol | None = None,
    ) -> pd.DataFrame:
        """Construct front + back ATM-call premium series.

        For each first-trading-day-of-month write date:

        1. Fetch chain.
        2. Pick ATM strike (closest to spot at write date).
        3. Front expiry = first chain expiry > 25 days; back
           expiry = first chain expiry > 55 days (~next month
           after front).
        4. Both legs priced via BS using the chain's per-expiry
           sigma at write; forward-evolved daily until front
           expiry (BOTH legs close at front expiry — the back
           is sold early at its remaining time value).
        """
        if not isinstance(underlying_prices, pd.Series):
            raise TypeError(
                f"underlying_prices must be a Series, got {type(underlying_prices).__name__}"
            )
        if not isinstance(underlying_prices.index, pd.DatetimeIndex):
            raise TypeError(
                "underlying_prices must have a DatetimeIndex, "
                f"got {type(underlying_prices.index).__name__}"
            )
        if underlying_prices.empty:
            return pd.DataFrame(
                {
                    self.front_leg_symbol: pd.Series(dtype=float),
                    self.back_leg_symbol: pd.Series(dtype=float),
                },
                index=underlying_prices.index,
            )

        feed = chain_feed if chain_feed is not None else self.chain_feed
        idx = underlying_prices.index
        prices_arr = underlying_prices.to_numpy(dtype=float)
        write_mask = _is_first_trading_day_of_month(idx)

        # Per-cycle state.
        strike: float | None = None
        front_expiry: date | None = None
        back_expiry: date | None = None
        front_sigma: float | None = None
        back_sigma: float | None = None

        front_premium = np.full(len(idx), _LEG_FLAT_FLOOR, dtype=float)
        back_premium = np.full(len(idx), _LEG_FLAT_FLOOR, dtype=float)

        for i in range(len(idx)):
            today = _to_date(idx[i])
            spot = prices_arr[i]

            # Close at front-month expiry: front goes to intrinsic,
            # back sold at remaining time value (BS-priced with
            # back-sigma + remaining TTE-to-back-expiry).
            if front_expiry is not None and today >= front_expiry:
                k = cast(float, strike)
                front_premium[i] = max(_LEG_FLAT_FLOOR, spot - k)
                back_tte = (cast(date, back_expiry) - today).days / _DAYS_PER_YEAR
                if back_tte > 0 and back_sigma is not None:
                    back_premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.call_price(spot, k, back_tte, _DEFAULT_RISK_FREE_RATE, back_sigma),
                    )
                else:
                    back_premium[i] = max(_LEG_FLAT_FLOOR, spot - k)
                strike = None
                front_expiry = None
                back_expiry = None
                front_sigma = None
                back_sigma = None

            # Write a new calendar spread.
            if write_mask[i] and front_expiry is None:
                try:
                    chain = feed.fetch_chain(self.underlying_symbol, idx[i].to_pydatetime())
                except (ValueError, NotImplementedError):
                    continue
                selected = self._select_calendar(chain, spot)
                if any(v is None for v in selected):
                    continue
                strike = cast(float, selected[0])
                front_expiry = cast(date, selected[1])
                back_expiry = cast(date, selected[2])
                front_sigma = cast(float, selected[3])
                back_sigma = cast(float, selected[4])
                front_tte = (front_expiry - today).days / _DAYS_PER_YEAR
                back_tte = (back_expiry - today).days / _DAYS_PER_YEAR
                if front_tte > 0:
                    front_premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.call_price(
                            spot,
                            strike,
                            front_tte,
                            _DEFAULT_RISK_FREE_RATE,
                            front_sigma,
                        ),
                    )
                if back_tte > 0:
                    back_premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.call_price(
                            spot,
                            strike,
                            back_tte,
                            _DEFAULT_RISK_FREE_RATE,
                            back_sigma,
                        ),
                    )
                continue

            # Daily mark-to-market: both legs priced with their
            # respective sigmas + decreasing TTE.
            if strike is not None and front_expiry is not None and back_expiry is not None:
                front_tte = (front_expiry - today).days / _DAYS_PER_YEAR
                back_tte = (back_expiry - today).days / _DAYS_PER_YEAR
                if front_tte > 0:
                    front_premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.call_price(
                            spot,
                            strike,
                            front_tte,
                            _DEFAULT_RISK_FREE_RATE,
                            cast(float, front_sigma),
                        ),
                    )
                if back_tte > 0:
                    back_premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.call_price(
                            spot,
                            strike,
                            back_tte,
                            _DEFAULT_RISK_FREE_RATE,
                            cast(float, back_sigma),
                        ),
                    )

        return pd.DataFrame(
            {self.front_leg_symbol: front_premium, self.back_leg_symbol: back_premium},
            index=underlying_prices.index,
        )

    def _select_calendar(
        self,
        chain: OptionChain,
        spot: float,
    ) -> tuple[float | None, date | None, date | None, float | None, float | None]:
        """Pick the (strike, front_expiry, back_expiry, front_sigma, back_sigma) tuple.

        ATM strike + two distinct expiries: front = first > 25 days,
        back = first > 55 days. Sigmas read from the chain's quotes
        for each expiry's ATM call.
        """
        as_of = _to_date(chain.as_of)
        sorted_expiries = sorted(chain.expiries())

        front_candidates = [e for e in sorted_expiries if (e - as_of).days >= _FRONT_MIN_DTE_DAYS]
        if not front_candidates:
            return None, None, None, None, None
        front_expiry = front_candidates[0]

        back_candidates = [e for e in sorted_expiries if (e - as_of).days >= _BACK_MIN_DTE_DAYS]
        if not back_candidates:
            return None, None, None, None, None
        back_expiry = back_candidates[0]
        if back_expiry <= front_expiry:
            return None, None, None, None, None

        # Closest-to-ATM call at the front expiry — use that strike for both legs.
        front_calls = chain.filter(expiry=front_expiry, right=OptionRight.CALL)
        if not front_calls:
            return None, None, None, None, None
        front_chosen = min(front_calls, key=lambda q: abs(q.strike - spot))
        strike = front_chosen.strike
        front_sigma = (
            front_chosen.iv if front_chosen.iv is not None and front_chosen.iv > 0 else None
        )
        if front_sigma is None:
            return None, None, None, None, None

        back_calls = chain.filter(expiry=back_expiry, right=OptionRight.CALL)
        # Match by strike to keep the spread strictly calendar (same K).
        back_match = next((q for q in back_calls if q.strike == strike), None)
        if back_match is None:
            return None, None, None, None, None
        back_sigma = back_match.iv if back_match.iv is not None and back_match.iv > 0 else None
        if back_sigma is None:
            return None, None, None, None, None
        return strike, front_expiry, back_expiry, front_sigma, back_sigma

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return calendar-spread weights.

        Mode 1 (full calendar spread):
            underlying = 0.0 (pure-options trade)
            front leg  = -1 on writes, +1 on closes (Amount, short)
            back leg   = +1 on writes, -1 on closes (Amount, long)
        Mode 2 (degenerate underlying-only):
            all weights = 0
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if self.underlying_symbol not in prices.columns:
            raise KeyError(
                f"prices must contain the underlying column "
                f"{self.underlying_symbol!r}; got columns={list(prices.columns)}"
            )
        if (prices[self.underlying_symbol] <= 0).any():
            raise ValueError(f"prices[{self.underlying_symbol!r}] must be strictly positive")

        weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        # Front leg: short.
        if self.front_leg_symbol in prices.columns:
            leg = prices[self.front_leg_symbol].to_numpy(dtype=float)
            write_mask, close_mask = _detect_lifecycle_events(leg)
            weights.loc[prices.index[write_mask], self.front_leg_symbol] = -1.0
            weights.loc[prices.index[close_mask], self.front_leg_symbol] = 1.0
        # Back leg: long.
        if self.back_leg_symbol in prices.columns:
            leg = prices[self.back_leg_symbol].to_numpy(dtype=float)
            write_mask, close_mask = _detect_lifecycle_events(leg)
            weights.loc[prices.index[write_mask], self.back_leg_symbol] = 1.0
            weights.loc[prices.index[close_mask], self.back_leg_symbol] = -1.0
        return weights


def _detect_lifecycle_events(leg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = len(leg)
    if n == 0:
        return np.zeros(0, dtype=bool), np.zeros(0, dtype=bool)
    is_open = leg > _LEG_PRICE_EPSILON
    prev_open = np.concatenate(([False], is_open[:-1]))
    next_open = np.concatenate((is_open[1:], [False]))
    write_mask = is_open & ~prev_open
    close_mask = is_open & ~next_open
    return write_mask, close_mask


with contextlib.suppress(ImportError):
    from alphakit.data.options import synthetic as _synthetic  # noqa: F401
