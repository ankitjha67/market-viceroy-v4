"""2-leg WEEKLY OTM put+call write on synthetic chains.

Phase 2 reframe of practitioner ``weekly_theta_harvest`` — see
``docs/phase-2-amendments.md`` 2026-05-01 entry "reframe
weekly_theta_harvest → weekly_short_volatility". "Theta
harvesting" is practitioner terminology with no academic anchor;
the reframe re-grounds the trade in the variance-risk-premium
literature (Carr-Wu 2009, Bondarenko 2014) which establishes the
short-vol premium across horizons including weekly.

Foundational paper
------------------
Carr, P. & Wu, L. (2009). *Variance Risk Premia*. Review of
Financial Studies, 22(3), 1311-1341.
https://doi.org/10.1093/rfs/hhn038

Carr & Wu document the variance risk premium across horizons
(monthly and weekly) and confirm the short-vol premium is
robust to horizon choice — selling weekly vol earns a positive
risk premium analogous to selling monthly vol.

Primary methodology
-------------------
Bondarenko, O. (2014). *Why Are Put Options So Expensive?*.
Quarterly Journal of Finance, 4(1), 1450015.
https://doi.org/10.1142/S2010139214500050

Bondarenko's empirical setup includes both monthly and weekly
horizon tests; the weekly OTM put/call write is the canonical
short-vol-at-weekly-horizon trade. Premia are smaller per cycle
(~$0.50-$1.00 vs monthly's $1-$5) but cycles are 4× more frequent
so cumulative annual premium is similar; the trade-off is
position-management overhead (weekly rolls vs monthly).

Differentiation from siblings
-----------------------------
* vs ``short_strangle_monthly`` (Commit 7, ρ ≈ 0.65-0.85):
  Same trade structure (short OTM put + short OTM call) but
  weekly cadence (4× more cycles per year) and tighter OTM
  default (5 % vs 10 %) since weekly options have less time
  value at deeper OTMs.
* vs ``variance_risk_premium_synthetic`` (Commit 11):
  Different mechanic — VRP-synth uses straddle replication
  per Carr-Wu §2; weekly_short_volatility is the simpler
  short-strangle-at-weekly-horizon variant.
* vs ``covered_call_systematic`` / ``cash_secured_put_systematic``:
  ρ ≈ 0.55-0.75 — same VRP exposure direction but different
  horizon and 2-leg vs 1-leg construction.

Bridge integration: 2 discrete legs
-----------------------------------
Same dispatch pattern as ``short_strangle_monthly``: declares
``discrete_legs = (put_leg_symbol, call_leg_symbol)``; bridge
applies ``Amount`` semantics to both legs and ``TargetPercent``
(default) to the underlying — but the strategy emits ``0.0`` on
the underlying (pure-options trade).

Implementation
--------------
Self-contained 2-leg strategy (NOT a composition wrapper over
monthly siblings, because the weekly cadence diverges from the
monthly inner strategies' first-trading-day-of-month rule).
Replicates the lifecycle state-machine pattern with
``_is_first_trading_day_of_week`` (Monday detection) instead of
``_is_first_trading_day_of_month``.

Each leg: walks the underlying-price index, identifies first
trading day of each calendar week as a *write date*, fetches
the chain, selects the closest OTM strike on the appropriate
side, and forward-evolves the BS-priced premium daily until the
chain's first weekly expiry > 3 days from write date.

The synthetic chain's expiry grid includes 4 weekly Fridays
(per ``alphakit.data.options.synthetic._weekly_fridays``); a
Monday write with a 3-day-DTE floor naturally selects the next
Friday's expiry (typically 4 days away).

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
_TARGET_MIN_DTE_DAYS: int = 3  # Monday → Friday expiry is 4 days


def _to_date(d: date | datetime | pd.Timestamp) -> date:
    if isinstance(d, pd.Timestamp):
        return d.date()
    if isinstance(d, datetime):
        return d.date()
    return d


def _is_first_trading_day_of_week(idx: pd.DatetimeIndex) -> np.ndarray:
    """Mark the first trading bar of each calendar week.

    A first-trading-day-of-week is the bar whose ISO week number
    differs from the previous bar's. For a standard B-frequency
    business-day index this is typically Monday (or Tuesday after
    a Monday holiday).
    """
    weeks = idx.isocalendar().week.to_numpy()
    is_first = np.zeros(len(idx), dtype=bool)
    is_first[0] = True
    is_first[1:] = weeks[1:] != weeks[:-1]
    return is_first


class WeeklyShortVolatility:
    """2-leg weekly short-vol strangle write on synthetic chains.

    Parameters
    ----------
    underlying_symbol
        Column name for the underlying. Defaults to ``"SPY"``.
        Pure-options trade — no underlying weight emitted.
    put_otm
        OTM offset for the short put leg. Defaults to ``0.05``
        (5 % OTM is the typical weekly setup; deeper OTMs have
        negligible premium at weekly horizons).
    call_otm
        OTM offset for the short call leg. Defaults to ``0.05``.
    chain_feed
        Optional explicit feed object.
    """

    name: str = "weekly_short_volatility"
    family: str = "options"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1142/S2010139214500050"  # Bondarenko 2014
    rebalance_frequency: str = "weekly"

    discrete_legs: tuple[str, ...]

    def __init__(
        self,
        *,
        underlying_symbol: str = "SPY",
        put_otm: float = 0.05,
        call_otm: float = 0.05,
        chain_feed: DataFeedProtocol | None = None,
    ) -> None:
        if not underlying_symbol:
            raise ValueError("underlying_symbol must be a non-empty string")
        if put_otm <= 0.0 or put_otm > 0.50:
            raise ValueError(f"put_otm must be in (0, 0.50], got {put_otm}")
        if call_otm <= 0.0 or call_otm > 0.50:
            raise ValueError(f"call_otm must be in (0, 0.50], got {call_otm}")
        self.underlying_symbol = underlying_symbol
        self.put_otm = put_otm
        self.call_otm = call_otm
        self._chain_feed = chain_feed
        self.discrete_legs = (self.put_leg_symbol, self.call_leg_symbol)

    @property
    def chain_feed(self) -> DataFeedProtocol:
        if self._chain_feed is not None:
            return self._chain_feed
        return FeedRegistry.get("synthetic-options")

    @property
    def put_leg_symbol(self) -> str:
        """Weekly short-put leg column name (W1 = 1-week)."""
        pct = round(self.put_otm * 100)
        return f"{self.underlying_symbol}_PUT_OTM{pct:02d}PCT_W1"

    @property
    def call_leg_symbol(self) -> str:
        pct = round(self.call_otm * 100)
        return f"{self.underlying_symbol}_CALL_OTM{pct:02d}PCT_W1"

    def make_legs_prices(
        self,
        underlying_prices: pd.Series,
        *,
        chain_feed: DataFeedProtocol | None = None,
    ) -> pd.DataFrame:
        """Construct both leg-premium series in one call.

        Walks the underlying-price index with weekly cadence
        (first-trading-day-of-week trigger), fetches the chain at
        each write date, selects the appropriate OTM put + call,
        and forward-evolves both legs' premia daily via BS.

        Returns a DataFrame indexed like ``underlying_prices`` with
        2 columns: put leg + call leg.
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
                    self.put_leg_symbol: pd.Series(dtype=float),
                    self.call_leg_symbol: pd.Series(dtype=float),
                },
                index=underlying_prices.index,
            )

        feed = chain_feed if chain_feed is not None else self.chain_feed
        idx = underlying_prices.index
        prices_arr = underlying_prices.to_numpy(dtype=float)
        write_mask = _is_first_trading_day_of_week(idx)

        # Two parallel state machines — one per leg.
        put_strike: float | None = None
        call_strike: float | None = None
        put_expiry: date | None = None
        call_expiry: date | None = None
        put_sigma: float | None = None
        call_sigma: float | None = None

        put_premium = np.full(len(idx), _LEG_FLAT_FLOOR, dtype=float)
        call_premium = np.full(len(idx), _LEG_FLAT_FLOOR, dtype=float)

        for i in range(len(idx)):
            today = _to_date(idx[i])
            spot = prices_arr[i]

            # Close put leg at expiry.
            if put_expiry is not None and today >= put_expiry:
                put_premium[i] = max(_LEG_FLAT_FLOOR, cast(float, put_strike) - spot)
                put_strike = None
                put_expiry = None
                put_sigma = None

            # Close call leg at expiry.
            if call_expiry is not None and today >= call_expiry:
                call_premium[i] = max(_LEG_FLAT_FLOOR, spot - cast(float, call_strike))
                call_strike = None
                call_expiry = None
                call_sigma = None

            # Write new positions.
            if write_mask[i] and put_expiry is None and call_expiry is None:
                try:
                    chain = feed.fetch_chain(self.underlying_symbol, idx[i].to_pydatetime())
                except (ValueError, NotImplementedError):
                    continue
                ps, pe, psig = self._select_put(chain, spot)
                cs, ce, csig = self._select_call(chain, spot)
                if ps is not None and pe is not None and psig is not None:
                    put_strike, put_expiry, put_sigma = ps, pe, psig
                    tte = (put_expiry - today).days / _DAYS_PER_YEAR
                    if tte > 0:
                        put_premium[i] = max(
                            _LEG_FLAT_FLOOR,
                            bs.put_price(spot, put_strike, tte, _DEFAULT_RISK_FREE_RATE, put_sigma),
                        )
                if cs is not None and ce is not None and csig is not None:
                    call_strike, call_expiry, call_sigma = cs, ce, csig
                    tte = (call_expiry - today).days / _DAYS_PER_YEAR
                    if tte > 0:
                        call_premium[i] = max(
                            _LEG_FLAT_FLOOR,
                            bs.call_price(
                                spot, call_strike, tte, _DEFAULT_RISK_FREE_RATE, call_sigma
                            ),
                        )
                continue

            # Daily mark-to-market on each leg between write and expiry.
            if put_strike is not None and put_expiry is not None and put_sigma is not None:
                tte = (put_expiry - today).days / _DAYS_PER_YEAR
                if tte > 0:
                    put_premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.put_price(spot, put_strike, tte, _DEFAULT_RISK_FREE_RATE, put_sigma),
                    )
                else:
                    put_premium[i] = max(_LEG_FLAT_FLOOR, put_strike - spot)
            if call_strike is not None and call_expiry is not None and call_sigma is not None:
                tte = (call_expiry - today).days / _DAYS_PER_YEAR
                if tte > 0:
                    call_premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.call_price(spot, call_strike, tte, _DEFAULT_RISK_FREE_RATE, call_sigma),
                    )
                else:
                    call_premium[i] = max(_LEG_FLAT_FLOOR, spot - call_strike)

        return pd.DataFrame(
            {self.put_leg_symbol: put_premium, self.call_leg_symbol: call_premium},
            index=underlying_prices.index,
        )

    def _select_put(
        self,
        chain: OptionChain,
        spot: float,
    ) -> tuple[float | None, date | None, float | None]:
        target_strike = spot * (1.0 - self.put_otm)
        as_of = _to_date(chain.as_of)
        candidate_expiries = sorted(
            e for e in chain.expiries() if (e - as_of).days >= _TARGET_MIN_DTE_DAYS
        )
        if not candidate_expiries:
            candidate_expiries = sorted(chain.expiries())
        if not candidate_expiries:
            return None, None, None
        expiry = candidate_expiries[0]
        puts = chain.filter(expiry=expiry, right=OptionRight.PUT)
        if not puts:
            return None, None, None
        otm_puts = [q for q in puts if q.strike <= target_strike]
        chosen = (
            sorted(otm_puts, key=lambda q: q.strike, reverse=True)[0]
            if otm_puts
            else min(puts, key=lambda q: q.strike)
        )
        sigma = chosen.iv if chosen.iv is not None and chosen.iv > 0 else None
        return chosen.strike, expiry, sigma

    def _select_call(
        self,
        chain: OptionChain,
        spot: float,
    ) -> tuple[float | None, date | None, float | None]:
        target_strike = spot * (1.0 + self.call_otm)
        as_of = _to_date(chain.as_of)
        candidate_expiries = sorted(
            e for e in chain.expiries() if (e - as_of).days >= _TARGET_MIN_DTE_DAYS
        )
        if not candidate_expiries:
            candidate_expiries = sorted(chain.expiries())
        if not candidate_expiries:
            return None, None, None
        expiry = candidate_expiries[0]
        calls = chain.filter(expiry=expiry, right=OptionRight.CALL)
        if not calls:
            return None, None, None
        otm_calls = [q for q in calls if q.strike >= target_strike]
        chosen = (
            sorted(otm_calls, key=lambda q: q.strike)[0]
            if otm_calls
            else max(calls, key=lambda q: q.strike)
        )
        sigma = chosen.iv if chosen.iv is not None and chosen.iv > 0 else None
        return chosen.strike, expiry, sigma

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return the 2-leg weekly short-strangle weights DataFrame.

        Mode 1 (full weekly strangle):
            underlying = 0.0 (pure-options trade)
            put leg    = -1 on writes, +1 on closes (Amount)
            call leg   = -1 on writes, +1 on closes (Amount)
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
        for leg_col in (self.put_leg_symbol, self.call_leg_symbol):
            if leg_col not in prices.columns:
                continue
            leg = prices[leg_col].to_numpy(dtype=float)
            write_mask, close_mask = _detect_lifecycle_events(leg)
            weights.loc[prices.index[write_mask], leg_col] = -1.0
            weights.loc[prices.index[close_mask], leg_col] = 1.0
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
