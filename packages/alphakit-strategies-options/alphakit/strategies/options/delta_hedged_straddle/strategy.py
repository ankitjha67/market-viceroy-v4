"""Long ATM straddle with daily delta hedge on synthetic chains.

Foundational paper
------------------
Black, F. & Scholes, M. (1973). *The Pricing of Options and
Corporate Liabilities*. Journal of Political Economy, 81(3),
637-654. https://doi.org/10.1086/260062

The canonical Black-Scholes derivation establishes the delta-
hedging argument: a continuously delta-hedged option position has
zero local exposure to the underlying's spot direction, leaving
the position's P&L proportional to *gamma × (realized variance −
implied variance)*. The delta-hedged straddle is the canonical
implementation of this argument in continuous time.

Primary methodology
-------------------
Carr, P. & Wu, L. (2009). *Variance Risk Premia*. Review of
Financial Studies, 22(3), 1311-1341.
https://doi.org/10.1093/rfs/hhn038

Carr & Wu document the variance risk premium empirically by
constructing delta-hedged option portfolios and measuring the
average P&L. Their finding: long-vol positions (long
delta-hedged straddles) earn negative expected returns — the
variance risk premium accrues to the writers, not the buyers.

This strategy is the **long-vol counterparty** to the short-vol
strategies in this family (`covered_call_systematic`,
`cash_secured_put_systematic`, `iron_condor_monthly`,
`short_strangle_monthly`, `weekly_short_volatility`). It exists
for users who want the long-vol exposure for portfolio
diversification (positive convexity, tail-risk insurance) and
who are willing to pay the VRP cost for that exposure.

Strategy structure
------------------
For each first trading day of a calendar month:

1. **Long call.** Strike = ``closest_chain_strike(spot_t)`` (ATM).
2. **Long put.** Strike = ``closest_chain_strike(spot_t)`` (same
   ATM strike — the straddle.)
3. **Expiry.** First chain expiry > 25 days from write.
4. **Daily delta hedge.** At each in-position bar, recompute the
   straddle's net delta (call delta + put delta = 2 N(d1) − 1)
   and adjust the underlying position to ``-net_delta`` (offset).
   The hedge is via the underlying's ``TargetPercent`` continuous
   weight.

Net P&L per cycle ≈ gamma × (realized_var − implied_var) × notional
— the model-free variance risk premium on a single underlying.
Carr-Wu document this is *negative on average* for S&P 500 OTM
straddles.

Bridge integration: 2 discrete legs + dynamic-hedge underlying
---------------------------------------------------------------
Strategy declares ``discrete_legs = (call_leg, put_leg)`` so the
bridge applies ``Amount`` semantics to both option legs (long
positions, +1 at write / -1 at close). The underlying gets
``TargetPercent`` (default) with a *time-varying* weight that
reflects the daily-delta-hedge ratio.

Stateful coupling
-----------------
``make_legs_prices`` walks the lifecycle and stores per-cycle
metadata (write date, expiry, strike, sigma) on
``self._cycles`` as a side effect. ``generate_signals`` reads
``self._cycles`` (along with the underlying spot from ``prices``)
to compute per-bar net delta and emit the hedge weight on the
underlying. This couples the two methods via internal state —
documented honestly as a deliberate design choice for Phase 2.
The alternative (storing metadata as auxiliary columns in the
prices DataFrame) was considered and rejected because
non-tradable metadata columns disturb vectorbt's mark-to-market.

If ``generate_signals`` is called *without* prior
``make_legs_prices`` (Mode 2: only underlying provided), the
strategy emits all-zero weights — degenerate no-trade backtest.

Cluster expectations
--------------------
* vs ``gamma_scalping_daily`` (Commit 10): ρ ≈ 0.85-0.95 (very
  similar mechanic — gamma scalping IS daily delta-hedged
  straddle with a different parameterisation).
* vs ``variance_risk_premium_synthetic`` (Commit 11):
  ρ ≈ 0.70-0.85 — different replication mechanic (Carr-Wu §2
  variance-swap weights vs simple straddle).
* vs short-vol siblings (covered_call_systematic etc.):
  ρ ≈ -0.7 to -0.9 (this is the LONG-vol counterparty;
  P&L sign is opposite).

Documented in ``known_failures.md``.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
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
_TARGET_MIN_DTE_DAYS: int = 25


@dataclass(frozen=True)
class _CycleMetadata:
    """Per-cycle state stored by make_legs_prices for use by generate_signals.

    The straddle's delta at any in-position bar is determined by:
    spot at that bar (from prices), strike (fixed at write date),
    days-to-expiry (fixed expiry date − today), and sigma (BS-IV
    used at write date, held constant within the cycle).
    """

    write_idx: int
    close_idx: int  # last in-position bar (one before expiry-flat)
    expiry: date
    strike: float
    sigma: float


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


class DeltaHedgedStraddle:
    """Long ATM straddle with daily delta hedge.

    Parameters
    ----------
    underlying_symbol
        Column name for the underlying. Defaults to ``"SPY"``.
    chain_feed
        Optional explicit feed object.
    """

    name: str = "delta_hedged_straddle"
    family: str = "options"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1093/rfs/hhn038"  # Carr-Wu 2009 (primary)
    rebalance_frequency: str = "daily"

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
        self.discrete_legs = (self.call_leg_symbol, self.put_leg_symbol)
        # Per-cycle state populated by make_legs_prices, consumed
        # by generate_signals for daily-delta-hedge weights.
        self._cycles: list[_CycleMetadata] = []

    @property
    def chain_feed(self) -> DataFeedProtocol:
        if self._chain_feed is not None:
            return self._chain_feed
        return FeedRegistry.get("synthetic-options")

    @property
    def call_leg_symbol(self) -> str:
        return f"{self.underlying_symbol}_CALL_ATM_STRADDLE_M1"

    @property
    def put_leg_symbol(self) -> str:
        return f"{self.underlying_symbol}_PUT_ATM_STRADDLE_M1"

    def make_legs_prices(
        self,
        underlying_prices: pd.Series,
        *,
        chain_feed: DataFeedProtocol | None = None,
    ) -> pd.DataFrame:
        """Construct both leg-premium series + per-cycle metadata.

        Side effect: populates ``self._cycles`` with the per-cycle
        (write_idx, close_idx, expiry, strike, sigma) tuples that
        ``generate_signals`` consumes for daily delta hedging.
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
            self._cycles = []
            return pd.DataFrame(
                {
                    self.call_leg_symbol: pd.Series(dtype=float),
                    self.put_leg_symbol: pd.Series(dtype=float),
                },
                index=underlying_prices.index,
            )

        feed = chain_feed if chain_feed is not None else self.chain_feed
        idx = underlying_prices.index
        prices_arr = underlying_prices.to_numpy(dtype=float)
        write_mask = _is_first_trading_day_of_month(idx)

        current_strike: float | None = None
        current_expiry: date | None = None
        current_sigma: float | None = None
        current_write_idx: int | None = None

        call_premium = np.full(len(idx), _LEG_FLAT_FLOOR, dtype=float)
        put_premium = np.full(len(idx), _LEG_FLAT_FLOOR, dtype=float)
        cycles: list[_CycleMetadata] = []

        for i in range(len(idx)):
            today = _to_date(idx[i])
            spot = prices_arr[i]

            # Close at expiry: record cycle metadata + price intrinsics.
            if current_expiry is not None and today >= current_expiry:
                call_premium[i] = max(_LEG_FLAT_FLOOR, spot - cast(float, current_strike))
                put_premium[i] = max(_LEG_FLAT_FLOOR, cast(float, current_strike) - spot)
                cycles.append(
                    _CycleMetadata(
                        write_idx=cast(int, current_write_idx),
                        close_idx=i,
                        expiry=current_expiry,
                        strike=cast(float, current_strike),
                        sigma=cast(float, current_sigma),
                    )
                )
                current_strike = None
                current_expiry = None
                current_sigma = None
                current_write_idx = None

            if write_mask[i] and current_expiry is None:
                try:
                    chain = feed.fetch_chain(self.underlying_symbol, idx[i].to_pydatetime())
                except (ValueError, NotImplementedError):
                    continue
                strike, expiry, sigma = self._select_atm(chain, spot)
                if strike is None or expiry is None or sigma is None:
                    continue
                current_strike = strike
                current_expiry = expiry
                current_sigma = sigma
                current_write_idx = i
                tte = (current_expiry - today).days / _DAYS_PER_YEAR
                if tte > 0:
                    call_premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.call_price(
                            spot, current_strike, tte, _DEFAULT_RISK_FREE_RATE, current_sigma
                        ),
                    )
                    put_premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.put_price(
                            spot, current_strike, tte, _DEFAULT_RISK_FREE_RATE, current_sigma
                        ),
                    )
                continue

            if (
                current_strike is not None
                and current_expiry is not None
                and current_sigma is not None
            ):
                tte = (current_expiry - today).days / _DAYS_PER_YEAR
                if tte > 0:
                    call_premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.call_price(
                            spot, current_strike, tte, _DEFAULT_RISK_FREE_RATE, current_sigma
                        ),
                    )
                    put_premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.put_price(
                            spot, current_strike, tte, _DEFAULT_RISK_FREE_RATE, current_sigma
                        ),
                    )
                else:
                    call_premium[i] = max(_LEG_FLAT_FLOOR, spot - current_strike)
                    put_premium[i] = max(_LEG_FLAT_FLOOR, current_strike - spot)

        # Flush trailing open cycle: if the window ends mid-cycle (between
        # write and expiry), generate_signals still needs cycle metadata
        # to emit hedge weights on the underlying for the trailing bars.
        # Treat the cycle as closing on the last bar of the window.
        if current_expiry is not None and current_write_idx is not None:
            cycles.append(
                _CycleMetadata(
                    write_idx=current_write_idx,
                    close_idx=len(idx) - 1,
                    expiry=current_expiry,
                    strike=cast(float, current_strike),
                    sigma=cast(float, current_sigma),
                )
            )
        self._cycles = cycles
        return pd.DataFrame(
            {self.call_leg_symbol: call_premium, self.put_leg_symbol: put_premium},
            index=underlying_prices.index,
        )

    def _select_atm(
        self,
        chain: OptionChain,
        spot: float,
    ) -> tuple[float | None, date | None, float | None]:
        """Pick the ATM strike + expiry + sigma for a new straddle write.

        ATM = closest grid strike to spot. The synthetic chain's
        1.00× spot strike is the obvious ATM choice on a clean grid.
        """
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
        # Closest-to-ATM call (smallest |strike − spot|).
        chosen = min(calls, key=lambda q: abs(q.strike - spot))
        sigma = chosen.iv if chosen.iv is not None and chosen.iv > 0 else None
        return chosen.strike, expiry, sigma

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return weights with daily-delta-hedge underlying + long
        straddle legs.

        Mode 1 (full delta-hedged straddle):
            underlying = -net_delta_t (TargetPercent, time-varying)
            call leg   = +1 on write, -1 on close (Amount, long)
            put leg    = +1 on write, -1 on close (Amount, long)
        Mode 2 (degenerate):
            all weights = 0 (no make_legs_prices side effect →
            no cycle metadata → no hedge → no trade)
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

        # Long-leg trades (Amount): +1 on write, -1 on close.
        for leg_col in (self.call_leg_symbol, self.put_leg_symbol):
            if leg_col not in prices.columns:
                continue
            leg = prices[leg_col].to_numpy(dtype=float)
            write_mask, close_mask = _detect_lifecycle_events(leg)
            weights.loc[prices.index[write_mask], leg_col] = 1.0  # long: BUY at write
            weights.loc[prices.index[close_mask], leg_col] = -1.0  # long: SELL at close

        # Daily delta hedge (TargetPercent): underlying weight =
        # -net_delta on each in-position bar. Requires self._cycles
        # populated by a prior make_legs_prices call.
        if self._cycles and self.call_leg_symbol in prices.columns:
            spot_arr = prices[self.underlying_symbol].to_numpy(dtype=float)
            hedge = np.zeros(len(prices.index), dtype=float)
            for cycle in self._cycles:
                # Hedge active from write_idx through close_idx
                # (inclusive of both endpoints).
                for i in range(cycle.write_idx, cycle.close_idx + 1):
                    today = _to_date(prices.index[i])
                    tte = (cycle.expiry - today).days / _DAYS_PER_YEAR
                    if tte <= 0:
                        continue
                    s = spot_arr[i]
                    call_d = bs.call_delta(
                        s, cycle.strike, tte, _DEFAULT_RISK_FREE_RATE, cycle.sigma
                    )
                    put_d = bs.put_delta(s, cycle.strike, tte, _DEFAULT_RISK_FREE_RATE, cycle.sigma)
                    net_delta = call_d + put_d  # long straddle: +call_delta + put_delta
                    hedge[i] = -net_delta  # offset to neutralise direction
            weights[self.underlying_symbol] = hedge
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
