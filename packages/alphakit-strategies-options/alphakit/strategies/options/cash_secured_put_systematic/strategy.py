"""Single-leg systematic 1-month 5 % OTM put write on synthetic chains.

Implementation notes
====================

Foundational paper
------------------
Whaley, R. E. (2002). *Return and Risk of CBOE Buy Write Monthly
Index*. Journal of Derivatives, 10(2), 35-42.
https://doi.org/10.3905/jod.2002.319188

The CBOE PUT index (cash-secured put-write index) is the
put-counterpart of BXM, constructed in parallel by CBOE on the
basis of Whaley's BXM methodology: deterministic monthly write of
a 1-month put against cash collateral, no path-conditional rolls.

Primary methodology
-------------------
Israelov, R. & Nielsen, L. N. (2014). *Covered Call Strategies:
One Fact and Eight Myths*. Financial Analysts Journal, 70(6), 23-31.
https://doi.org/10.2469/faj.v70.n6.5

Israelov & Nielsen exploit put-call parity: a covered call (long
underlying + short call) has the same payoff (ex-dividends) as
``+cash − short put`` at the same strike and expiry. They show
that the BXM-style covered-call return decomposition (equity beta
+ short volatility + implicit short put) maps directly to the
put-write decomposition (cash + short put), and conclude that
PUT-style cash-secured-put-writes earn the same variance risk
premium as BXM-style covered calls — with mechanically simpler
exposure (no equity-leg cap-and-floor profile).

Why two papers
--------------
Whaley (2002) is the seminal *index construction* paper; CBOE PUT
applies the same construction to puts. Israelov-Nielsen (2014)
provides the theoretical decomposition that motivates this
strategy as the put-side equivalent of ``covered_call_systematic``,
making the put-call-parity argument rigorous. The strategy
*replicates* Israelov-Nielsen's put-write factor model on synthetic
chains; we cite Whaley 2002 as the foundational index-construction
reference.

Differentiation from Phase 1 ``cash_secured_put_proxy``
-------------------------------------------------------
Phase 1's ``cash_secured_put_proxy`` (volatility family, ADR-002
_proxy suffix) is a *realized-vol overlay* anchored on Ungar &
Moran 2009. It does *not* consume an option chain — same proxy
mechanic as Phase 1's ``covered_call_proxy`` (long-equity weight
scaled by ``target_vol / realized_vol``).

Phase 2's ``cash_secured_put_systematic`` consumes a real
:class:`~alphakit.core.data.OptionChain` from the synthetic-options
adapter (ADR-005). It expresses its position in two columns —
implicit cash collateral (the underlying held inactive) plus a
real short-put leg priced from the chain.

Both slugs co-exist on main: the proxy is the Phase 1
realized-vol-based approximation; the systematic version is the
canonical Phase 2 form with chain-driven leg pricing.

Expected cluster correlation with the Phase 1 proxy:
ρ ≈ 0.85-0.95 in neutral-to-rising-vol regimes; lower (0.5-0.7)
in strong-trending regimes. Documented in ``known_failures.md``.

Differentiation from sibling ``covered_call_systematic``
--------------------------------------------------------
Put-call parity equivalence: long underlying + short call has the
*same payoff* (ex-dividends, European exercise) as
+cash − short put when the strikes and expiries match. The
synthetic chain prices both legs off the same Black-Scholes
diffusion, so on synthetic data the two strategies' P&L is
near-identical in *magnitude* — only the leg construction differs.

Expected cluster correlation: ρ ≈ 0.95-1.00 with
``covered_call_systematic``. Both ship as canonical Phase 2 forms
because users may prefer one expression over the other based on
margin treatment, capital efficiency, or compliance constraints,
and a real (skewed, non-European) market would diverge from the
synthetic-chain put-call parity.

Bridge integration: ``discrete_legs`` metadata
----------------------------------------------
Same dispatch mechanism as ``covered_call_systematic`` (see that
module's docstring or
``packages/alphakit-strategies-options/alphakit/strategies/options/covered_call_systematic/strategy.py``
for the canonical explanation). The synthetic short-put leg is
written-and-held for ~30 days, declared in
``discrete_legs = (put_leg_symbol,)``; the
:mod:`alphakit.bridges.vectorbt_bridge` dispatches
``SizeType.Amount`` for the leg via
:func:`~alphakit.core.protocols.get_discrete_legs`.

Cross-reference: ``docs/phase-2-amendments.md`` 2026-05-01 entry
"bridge architecture extension for discrete-traded legs".

Published rules (Israelov & Nielsen 2014, PUT-aligned)
------------------------------------------------------
For each first trading day of a calendar month *t*:

1. **Strike.** ``K = closest_chain_strike(spot_t × (1 - otm_pct))``
   — default ``otm_pct = 0.05`` (PUT index uses ATM; the 5 % OTM
   variant trades premium income for less assignment risk in
   strong-downside regimes). Snap to the *largest* available chain
   strike ≤ ``spot × 0.95``.
2. **Expiry.** First chain expiry strictly later than 25 days from
   the write date.
3. **Position.** Cash collateral on the underlying long, short 1
   unit of the put identified by (strike, expiry). Hold through
   expiry; on the next first-trading-day-of-month, write a fresh
   put.

Output convention
-----------------
Mirrors ``covered_call_systematic``'s dual-mode pattern:

Mode 1 (canonical, full cash-secured put):
    prices columns ⊇ [underlying_symbol, put_leg_symbol]
    weights:
        underlying = +1.0 every bar (cash collateral expressed as
                     long underlying via TargetPercent semantics —
                     under put-call parity this is the natural
                     book representation)
        put leg    = -1.0 on write bars, +1.0 on close bars,
                     0.0 elsewhere (Amount semantics)
        other     = 0.0
Mode 2 (buy-and-hold approximation, benchmark runner fallback):
    prices columns ⊇ [underlying_symbol]
    weights:
        underlying = +1.0 every bar
        other     = 0.0

The "underlying = +1" convention in Mode 1 reflects the CBOE PUT
index's full-collateralization assumption: cash equal to the
strike value is reserved per write so that on assignment the
position is fully covered. Expressed as long underlying + short
put, this is the put-call-parity-equivalent of long underlying +
short call (= covered call).

Synthetic-options adapter integration
-------------------------------------
:meth:`make_put_leg_prices` is the put-side analogue of
``make_call_leg_prices``. It walks the underlying-price index,
identifies first-trading-day-of-month write dates, fetches the
chain, selects the largest OTM put strike ≤ ``spot × (1 - otm_pct)``,
and forward-evolves the put premium daily via
:func:`alphakit.data.options.bs.put_price` until expiry, then
floors at intrinsic (``max(0, K - S_T)``).

The 1e-6 flat floor and 1e-3 lifecycle epsilon convention is
identical to ``covered_call_systematic``; the bridge requires
positive prices on every bar even outside the in-position window,
and the 3-OOM separation between floor and epsilon prevents
false-positive lifecycle events.

Methodology deviations from the published PUT construction
----------------------------------------------------------
* **Synthetic chain has flat IV across strikes** (no skew). Real
  PUT writes are typically deep-OTM (5-10 %) where put-skew makes
  the premium materially higher than ATM-IV-priced. The synthetic
  chain underprices these writes.
* **No bid-ask spread / financing model.** Real CSPs face
  bid-ask drag plus margin-financing on the cash collateral.
* **Calendar-month-start writes vs. third-Friday writes.** Same
  convention as ``covered_call_systematic``.
* **OTM-expiry close approximation.** Same logic as
  ``covered_call_systematic``: when the put expires
  out-of-the-money the leg's expiry-bar price is the flat floor
  (intrinsic = 0), and the close fires one bar early at a small
  residual time-value premium. Per-cycle P&L is approximately
  1-2 % short of the analytic premium-minus-zero-intrinsic.

Edge cases — same as ``covered_call_systematic``.
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

# Default risk-free rate matches the synthetic-options adapter's
# placeholder. Phase 3 sources this from FRED per as-of date.
_DEFAULT_RISK_FREE_RATE: float = 0.045

# Trading-days-per-year — matches the synthetic-options adapter
# convention (calendar days / 365).
_DAYS_PER_YEAR: float = 365.0

# Flat floor + lifecycle epsilon — same convention as
# ``covered_call_systematic`` (3 orders of magnitude separation).
_LEG_FLAT_FLOOR: float = 1e-6
_LEG_PRICE_EPSILON: float = 1e-3


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


class CashSecuredPutSystematic:
    """Single-leg systematic 1-month 5 % OTM put write on synthetic chains.

    Parameters
    ----------
    underlying_symbol
        Column name for the underlying. Defaults to ``"SPY"``.
    otm_pct
        Out-of-the-money offset for the written put (decimal,
        ``0.05`` for 5 % OTM). Must be > 0 and ≤ 0.50.
    chain_feed
        Optional explicit feed object for chain access. When
        ``None`` (default), resolves
        ``FeedRegistry.get("synthetic-options")`` lazily.
    """

    name: str = "cash_secured_put_systematic"
    family: str = "options"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.2469/faj.v70.n6.5"  # Israelov-Nielsen 2014 (primary)
    rebalance_frequency: str = "monthly"

    discrete_legs: tuple[str, ...]

    def __init__(
        self,
        *,
        underlying_symbol: str = "SPY",
        otm_pct: float = 0.05,
        chain_feed: DataFeedProtocol | None = None,
    ) -> None:
        if not underlying_symbol:
            raise ValueError("underlying_symbol must be a non-empty string")
        if otm_pct < 0.0:
            raise ValueError(f"otm_pct must be >= 0, got {otm_pct}")
        if otm_pct > 0.50:
            raise ValueError(f"otm_pct must be <= 0.50, got {otm_pct}")
        self.underlying_symbol = underlying_symbol
        self.otm_pct = otm_pct
        self._chain_feed = chain_feed
        self.discrete_legs = (self.put_leg_symbol,)

    @property
    def chain_feed(self) -> DataFeedProtocol:
        if self._chain_feed is not None:
            return self._chain_feed
        return FeedRegistry.get("synthetic-options")

    @property
    def put_leg_symbol(self) -> str:
        """Synthetic short-put leg column name.

        Format: ``f"{underlying}_PUT_OTM{round(otm_pct*100):02d}PCT_M1"`` —
        e.g. ``"SPY_PUT_OTM05PCT_M1"`` for the 5 % OTM 1-month put
        on SPY.
        """
        pct = round(self.otm_pct * 100)
        return f"{self.underlying_symbol}_PUT_OTM{pct:02d}PCT_M1"

    def make_put_leg_prices(
        self,
        underlying_prices: pd.Series,
        *,
        chain_feed: DataFeedProtocol | None = None,
    ) -> pd.Series:
        """Construct the synthetic short-put premium series.

        Put-side analogue of
        :meth:`CoveredCallSystematic.make_call_leg_prices`. For each
        first-trading-day-of-month write date, fetch the option
        chain, select the largest OTM-put strike ≤
        ``spot × (1 - otm_pct)`` with the first chain expiry
        clearing a 25-day-DTE floor, and forward-evolve the put
        premium daily via :func:`bs.put_price`. At expiry the
        leg's price is intrinsic (``max(0, K - S_T)``); between
        expiry and the next write date it's the flat floor.

        Returns
        -------
        pd.Series
            Index aligned to ``underlying_prices``. Values are put
            premia (≥ flat floor 1e-6).
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
            return pd.Series(dtype=float, name=self.put_leg_symbol)

        feed = chain_feed if chain_feed is not None else self.chain_feed
        idx = underlying_prices.index
        prices_arr = underlying_prices.to_numpy(dtype=float)
        write_mask = _is_first_trading_day_of_month(idx)

        current_strike: float | None = None
        current_expiry: date | None = None
        current_sigma: float | None = None
        premium = np.full(len(idx), _LEG_FLAT_FLOOR, dtype=float)

        for i in range(len(idx)):
            today = _to_date(idx[i])
            spot = prices_arr[i]

            if current_expiry is not None and today >= current_expiry:
                premium[i] = max(_LEG_FLAT_FLOOR, cast(float, current_strike) - spot)
                current_strike = None
                current_expiry = None
                current_sigma = None

            if write_mask[i] and current_expiry is None:
                try:
                    chain = feed.fetch_chain(self.underlying_symbol, idx[i].to_pydatetime())
                except (ValueError, NotImplementedError):
                    continue
                strike, expiry, sigma = self._select_put(chain, spot)
                if strike is None or expiry is None or sigma is None:
                    continue
                current_strike = strike
                current_expiry = expiry
                current_sigma = sigma
                tte = (current_expiry - today).days / _DAYS_PER_YEAR
                if tte > 0:
                    premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.put_price(
                            spot,
                            current_strike,
                            tte,
                            _DEFAULT_RISK_FREE_RATE,
                            current_sigma,
                        ),
                    )
                continue

            if current_strike is not None and current_expiry is not None:
                tte = (current_expiry - today).days / _DAYS_PER_YEAR
                if tte > 0:
                    premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.put_price(
                            spot,
                            current_strike,
                            tte,
                            _DEFAULT_RISK_FREE_RATE,
                            cast(float, current_sigma),
                        ),
                    )
                else:
                    premium[i] = max(_LEG_FLAT_FLOOR, current_strike - spot)

        return pd.Series(premium, index=underlying_prices.index, name=self.put_leg_symbol)

    def _select_put(
        self,
        chain: OptionChain,
        spot: float,
    ) -> tuple[float | None, date | None, float | None]:
        """Pick the (strike, expiry, sigma) for the new put write.

        Mirrors ``covered_call_systematic._select_call`` with the
        direction reversed: the put strike is the *largest*
        available chain strike ≤ ``spot × (1 - otm_pct)`` (closest
        OTM-put to the target). Falls back to the smallest
        available strike if no OTM-put clears the threshold
        (extreme rally past the 0.80× lower grid bound).
        """
        target_strike = spot * (1.0 - self.otm_pct)
        as_of = _to_date(chain.as_of)
        target_min_dte = 25
        candidate_expiries = sorted(
            e for e in chain.expiries() if (e - as_of).days >= target_min_dte
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
        if otm_puts:
            otm_puts.sort(key=lambda q: q.strike, reverse=True)
            chosen = otm_puts[0]
        else:
            chosen = min(puts, key=lambda q: q.strike)
        sigma = chosen.iv if chosen.iv is not None and chosen.iv > 0 else None
        return chosen.strike, expiry, sigma

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a cash-secured-put weights DataFrame.

        Mode 1 (both legs present):
            underlying = +1.0 every bar (cash collateral as
                         long-underlying TargetPercent)
            put leg    = -1.0 on writes, +1.0 on closes, 0 else
                         (Amount via discrete_legs)
        Mode 2 (only underlying):
            underlying = +1.0 every bar (buy-and-hold approximation)

        Lifecycle events on the put leg are detected via
        positive-to-zero (close) and zero-to-positive (write)
        discontinuities — same algorithm as
        ``covered_call_systematic``.
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
        weights[self.underlying_symbol] = 1.0
        if self.put_leg_symbol in prices.columns:
            leg = prices[self.put_leg_symbol].to_numpy(dtype=float)
            write_mask, close_mask = _detect_lifecycle_events(leg)
            weights.loc[prices.index[write_mask], self.put_leg_symbol] = -1.0
            weights.loc[prices.index[close_mask], self.put_leg_symbol] = 1.0
        return weights


def _detect_lifecycle_events(leg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Detect write/close events on the put leg.

    Identical algorithm to
    ``covered_call_systematic._detect_lifecycle_events``. The
    1e-3 lifecycle epsilon distinguishes in-position bars (BS-
    priced premium) from flat bars (1e-6 floor).
    """
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
