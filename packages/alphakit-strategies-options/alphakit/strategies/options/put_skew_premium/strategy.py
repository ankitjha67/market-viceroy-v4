"""Risk-reversal short OTM put + long OTM call (put-skew-premium harvest).

⚠ SUBSTRATE CAVEAT
==================
The synthetic-options adapter (ADR-005) has **flat implied
volatility across strikes by construction**. This strategy's
economic content — the put-skew premium (real OTM puts trade
richer than OTM calls due to left-tail demand) — **cannot be
properly tested on this substrate**. The synthetic chain prices
the OTM put at the same IV as the OTM call, so the risk-reversal
P&L collapses to a directional-call P&L plus statistical noise.

The strategy ships in Phase 2 as a faithful implementation of
the published methodology with documented Phase 3 verification
path against real options chains via Polygon (ADR-004 stub).
The synthetic backtest is **uninformative for the specific
premium this strategy targets** and should not be used to
evaluate the strategy's expected return.

Foundational paper
------------------
Bakshi, G., Kapadia, N. & Madan, D. (2003). *Stock Return
Characteristics, Skew Laws, and the Differential Pricing of
Individual Equity Options*. Review of Financial Studies, 16(1),
101-143. https://doi.org/10.1093/rfs/16.1.0101

Bakshi-Kapadia-Madan derive the model-free risk-neutral skew
formula and document the *put-skew premium* on individual
equities and indices: real OTM puts are systematically more
expensive (higher IV) than real OTM calls at the same |delta|,
reflecting left-tail demand for portfolio protection.

Primary methodology
-------------------
Garleanu, N., Pedersen, L. H. & Poteshman, A. M. (2009).
*Demand-Based Option Pricing*. Review of Financial Studies,
22(10), 4259-4299. https://doi.org/10.1093/rfs/hhp005

Garleanu-Pedersen-Poteshman provide the *demand-based*
microfoundation for the put-skew premium: end-user demand for
portfolio insurance pushes OTM-put prices above their no-arbitrage
levels, leaving a systematic short-skew premium for sellers.
The risk-reversal trade (short OTM put + long OTM call) is the
canonical isolated capture of this premium.

Strategy structure
------------------
For each first trading day of a calendar month:

1. **Short OTM put** at ``spot × (1 - put_otm)`` (default 5 % OTM).
2. **Long OTM call** at ``spot × (1 + call_otm)`` (default 5 % OTM).
3. **Expiry.** First chain expiry > 25 days from write.
4. **Position sizing.** -1 short put + +1 long call per cycle.
   Net premium received = put_premium - call_premium (positive
   on real chains where put-skew makes the put more expensive;
   approximately zero on the synthetic chain).
5. **Close.** Both legs close at expiry, each at intrinsic.

The trade is *bullishly directional* (long call delta + short
put delta both add to net positive delta on real chains).
Documented under "Cluster overlap" in ``known_failures.md``.

Bridge integration
------------------
2 discrete legs: short put (-1 at write / +1 at close) + long
call (+1 at write / -1 at close). Underlying weight 0.

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
_TARGET_MIN_DTE_DAYS: int = 25


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


class PutSkewPremium:
    """Risk-reversal short OTM put + long OTM call (put-skew-premium harvest).

    ⚠ See module docstring substrate caveat — this strategy's
    target premium is NOT testable on the synthetic-options
    chain's flat-IV substrate. Phase 3 with Polygon required for
    proper evaluation.

    Parameters
    ----------
    underlying_symbol
        Column name for the underlying. Defaults to ``"SPY"``.
    put_otm
        OTM offset for the short-put leg. Defaults to ``0.05``.
    call_otm
        OTM offset for the long-call leg. Defaults to ``0.05``.
    chain_feed
        Optional explicit feed object.
    """

    name: str = "put_skew_premium"
    family: str = "options"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1093/rfs/hhp005"  # Garleanu-Pedersen-Poteshman 2009
    rebalance_frequency: str = "monthly"

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
        pct = round(self.put_otm * 100)
        return f"{self.underlying_symbol}_PUT_OTM{pct:02d}PCT_RR_M1"

    @property
    def call_leg_symbol(self) -> str:
        pct = round(self.call_otm * 100)
        return f"{self.underlying_symbol}_CALL_OTM{pct:02d}PCT_RR_M1"

    def make_legs_prices(
        self,
        underlying_prices: pd.Series,
        *,
        chain_feed: DataFeedProtocol | None = None,
    ) -> pd.DataFrame:
        """Construct both leg-premium series.

        Standard 2-leg lifecycle: write at first-trading-day-of-month,
        close at chain expiry. BS-priced premia using the chain's
        per-DTE-bucket sigma.

        ⚠ On the flat-IV synthetic chain, put_premium ≈ call_premium
        for matched OTM offsets, so the risk-reversal's economic
        content (skew premium) is approximately zero by construction.
        Documented in known_failures.md.
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
        write_mask = _is_first_trading_day_of_month(idx)

        put_strike: float | None = None
        call_strike: float | None = None
        expiry: date | None = None
        put_sigma: float | None = None
        call_sigma: float | None = None

        put_premium = np.full(len(idx), _LEG_FLAT_FLOOR, dtype=float)
        call_premium = np.full(len(idx), _LEG_FLAT_FLOOR, dtype=float)

        for i in range(len(idx)):
            today = _to_date(idx[i])
            spot = prices_arr[i]

            if expiry is not None and today >= expiry:
                put_premium[i] = max(_LEG_FLAT_FLOOR, cast(float, put_strike) - spot)
                call_premium[i] = max(_LEG_FLAT_FLOOR, spot - cast(float, call_strike))
                put_strike = None
                call_strike = None
                expiry = None
                put_sigma = None
                call_sigma = None

            if write_mask[i] and expiry is None:
                try:
                    chain = feed.fetch_chain(self.underlying_symbol, idx[i].to_pydatetime())
                except (ValueError, NotImplementedError):
                    continue
                ps, cs, exp, psig, csig = self._select_risk_reversal(chain, spot)
                if ps is None or cs is None or exp is None or psig is None or csig is None:
                    continue
                put_strike = ps
                call_strike = cs
                expiry = exp
                put_sigma = psig
                call_sigma = csig
                tte = (expiry - today).days / _DAYS_PER_YEAR
                if tte > 0:
                    put_premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.put_price(spot, put_strike, tte, _DEFAULT_RISK_FREE_RATE, put_sigma),
                    )
                    call_premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.call_price(spot, call_strike, tte, _DEFAULT_RISK_FREE_RATE, call_sigma),
                    )
                continue

            if (
                put_strike is not None
                and call_strike is not None
                and expiry is not None
                and put_sigma is not None
                and call_sigma is not None
            ):
                tte = (expiry - today).days / _DAYS_PER_YEAR
                if tte > 0:
                    put_premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.put_price(spot, put_strike, tte, _DEFAULT_RISK_FREE_RATE, put_sigma),
                    )
                    call_premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.call_price(spot, call_strike, tte, _DEFAULT_RISK_FREE_RATE, call_sigma),
                    )
                else:
                    put_premium[i] = max(_LEG_FLAT_FLOOR, put_strike - spot)
                    call_premium[i] = max(_LEG_FLAT_FLOOR, spot - call_strike)

        return pd.DataFrame(
            {self.put_leg_symbol: put_premium, self.call_leg_symbol: call_premium},
            index=underlying_prices.index,
        )

    def _select_risk_reversal(
        self,
        chain: OptionChain,
        spot: float,
    ) -> tuple[float | None, float | None, date | None, float | None, float | None]:
        """Pick (put_strike, call_strike, expiry, put_sigma, call_sigma)."""
        as_of = _to_date(chain.as_of)
        candidate_expiries = sorted(
            e for e in chain.expiries() if (e - as_of).days >= _TARGET_MIN_DTE_DAYS
        )
        if not candidate_expiries:
            candidate_expiries = sorted(chain.expiries())
        if not candidate_expiries:
            return None, None, None, None, None
        expiry = candidate_expiries[0]

        put_target = spot * (1.0 - self.put_otm)
        call_target = spot * (1.0 + self.call_otm)

        puts = chain.filter(expiry=expiry, right=OptionRight.PUT)
        calls = chain.filter(expiry=expiry, right=OptionRight.CALL)
        if not puts or not calls:
            return None, None, None, None, None

        otm_puts = [q for q in puts if q.strike <= put_target]
        put_chosen = (
            sorted(otm_puts, key=lambda q: q.strike, reverse=True)[0]
            if otm_puts
            else min(puts, key=lambda q: q.strike)
        )
        otm_calls = [q for q in calls if q.strike >= call_target]
        call_chosen = (
            sorted(otm_calls, key=lambda q: q.strike)[0]
            if otm_calls
            else max(calls, key=lambda q: q.strike)
        )

        psig = put_chosen.iv if put_chosen.iv is not None and put_chosen.iv > 0 else None
        csig = call_chosen.iv if call_chosen.iv is not None and call_chosen.iv > 0 else None
        if psig is None or csig is None:
            return None, None, None, None, None
        return put_chosen.strike, call_chosen.strike, expiry, psig, csig

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return risk-reversal weights.

        Mode 1 (full risk reversal):
            underlying = 0.0 (pure-options trade)
            put leg    = -1 on writes, +1 on closes (Amount, short)
            call leg   = +1 on writes, -1 on closes (Amount, long)
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
        # Short put: -1 at write, +1 at close.
        if self.put_leg_symbol in prices.columns:
            leg = prices[self.put_leg_symbol].to_numpy(dtype=float)
            write_mask, close_mask = _detect_lifecycle_events(leg)
            weights.loc[prices.index[write_mask], self.put_leg_symbol] = -1.0
            weights.loc[prices.index[close_mask], self.put_leg_symbol] = 1.0
        # Long call: +1 at write, -1 at close.
        if self.call_leg_symbol in prices.columns:
            leg = prices[self.call_leg_symbol].to_numpy(dtype=float)
            write_mask, close_mask = _detect_lifecycle_events(leg)
            weights.loc[prices.index[write_mask], self.call_leg_symbol] = 1.0
            weights.loc[prices.index[close_mask], self.call_leg_symbol] = -1.0
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
