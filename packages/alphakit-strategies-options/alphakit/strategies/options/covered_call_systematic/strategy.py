"""Single-leg systematic 1-month 2 % OTM call write on synthetic chains.

Implementation notes
====================

Foundational paper
------------------
Whaley, R. E. (2002). *Return and Risk of CBOE Buy Write Monthly
Index*. Journal of Derivatives, 10(2), 35-42.
https://doi.org/10.3905/jod.2002.319188

Whaley constructs the CBOE BXM index as a passive benchmark of the
1-month covered-call write: long the S&P 500 cash index, short a
1-month at-the-money S&P 500 call written each third Friday and
held to expiry. The construction is deterministic — no
discretionary timing, no path-conditional rolls — so the resulting
index is the canonical published benchmark for systematic monthly
covered-call writing.

Primary methodology
-------------------
Israelov, R. & Nielsen, L. N. (2014). *Covered Call Strategies:
One Fact and Eight Myths*. Financial Analysts Journal, 70(6), 23-31.
https://doi.org/10.2469/faj.v70.n6.5

Israelov & Nielsen decompose covered-call returns into three
factors: equity beta, short volatility, and an implicit short put
(via put-call parity). They confirm that the BXM-style monthly
write earns a positive Sharpe in OOS data primarily as compensation
for the variance risk premium, *not* from the equity premium alone.
A 2 % OTM offset (vs. exactly ATM in the BXM definition) trades
some premium income for upside participation — the Israelov-Nielsen
analysis shows the adjusted Sharpe is similar to ATM-BXM in most
regimes and noticeably better in strong-uptrend regimes (less
called-away P&L drag).

Why two papers
--------------
Whaley (2002) is the seminal *index construction* paper but the BXM
index uses an exactly-ATM strike. The strategy here implements a
parametric variant (default 2 % OTM) which is the form Israelov &
Nielsen (2014) study and which matches how covered calls are
written in practice. We anchor the implementation on
Israelov-Nielsen because that is the paper whose decomposition
(equity beta + short vol + short put) the strategy *replicates*; we
cite Whaley 2002 as the foundational reference for the systematic
monthly-write construction.

Differentiation from Phase 1 ``covered_call_proxy``
---------------------------------------------------
Phase 1's ``covered_call_proxy`` (volatility family, ADR-002 _proxy
suffix) is a *realized-vol overlay*: long equity scaled by
``target_vol / realized_vol`` capped at ``max_leverage``. It does
*not* consume an option chain — the "covered call" framing is a
proxy for vol-selling exposure derived purely from price returns.

Phase 2's ``covered_call_systematic`` consumes a real
:class:`~alphakit.core.data.OptionChain` from the synthetic-options
adapter (ADR-005, Phase 2 Session 2C). The chain provides explicit
strike grid, multi-expiry term structure, and Black-Scholes-priced
quotes including greeks. The strategy expresses its position in
two columns — long underlying + short call — rather than as a
modulated equity weight. This is the canonical Phase 2 form of the
covered-call trade; the Phase 1 _proxy slug remains on main as the
realized-vol-based approximation it always was.

Expected cluster correlation with the _proxy: ρ ≈ 0.85-0.95 in
neutral-to-rising-vol regimes (both express the same short-vol
premium); lower in trending equity regimes where the synthetic
chain's flat-IV substrate diverges from realized-vol dynamics.
Documented in ``known_failures.md``.

Bridge integration: ``discrete_legs`` metadata
----------------------------------------------
The synthetic short-call leg is **written-and-held** for ~30 days,
not continuously rebalanced. Under the default
:class:`vectorbt SizeType.TargetPercent` semantics every existing
strategy uses, a static ``weight = -1.0`` on the call leg every
bar would mean "rebalance to −100 % of equity in this asset every
bar," causing the bridge to sell ever-more contracts as the
premium decays from ~$5 → $0 across the monthly cycle and
producing runaway short P&L.

This strategy declares ``discrete_legs = (call_leg_symbol,)`` —
an optional :class:`~alphakit.core.protocols.StrategyProtocol`
attribute introduced for Session 2F (see
``docs/phase-2-amendments.md`` 2026-05-01 entry "bridge
architecture extension for discrete-traded legs"). The
:mod:`alphakit.bridges.vectorbt_bridge` reads this via
:func:`~alphakit.core.protocols.get_discrete_legs` and dispatches
``SizeType.Amount`` for the declared columns,
``SizeType.TargetPercent`` for the rest. Under ``Amount`` semantics,
the strategy's emitted weight at each bar is interpreted as
**number of shares traded this bar** — not target dollar
exposure — so a clean -1 on the write bar opens a one-contract
short position that is held through the cycle without
accumulating.

Published rules (Israelov & Nielsen 2014, BXM-aligned)
------------------------------------------------------
For each first trading day of a calendar month *t*:

1. **Write date.** First trading day of each calendar month. The
   exact CBOE BXM index rolls on the third Friday but the
   calendar-month-start convention matches how the 2 % OTM variant
   is typically tracked.
2. **Strike.** ``K = closest_chain_strike(spot_t × (1 + otm_pct))``
   — default ``otm_pct = 0.02``. Snap to the smallest available
   chain strike ≥ ``spot × 1.02``. The synthetic chain provides
   a 9-strike grid spanning 0.80×-1.20× spot.
3. **Expiry.** First chain expiry strictly later than 25 days from
   the write date — i.e. the first monthly third-Friday after the
   next month-start. Falls back to the latest available chain
   expiry only if no expiry clears the 25-day floor.
4. **Position.** Long 1 unit underlying, short 1 unit of the call
   identified by (strike, expiry). Hold through expiry; on the
   next first-trading-day-of-month, write a fresh call.

Output convention
-----------------
This strategy emits **two-column weights** when both legs are
available in the input ``prices`` DataFrame, otherwise single-
column buy-and-hold of the underlying (Mode 2). The dual-mode
exists because the standard
:class:`alphakit.bench.runner.BenchmarkRunner` provides only the
underlying's price column from the universe in ``config.yaml``;
the synthetic call leg's premium series must be constructed
externally (see :meth:`make_call_leg_prices` below) and appended
to the input panel before invoking the strategy. Session 2H's
benchmark-runner refactor will wire up the call-leg construction
so the standard benchmark exercises the canonical Mode 1 path.

Mode 1 (canonical, full covered call):
    prices columns ⊇ [underlying_symbol, call_leg_symbol]
    weights:
        underlying    = +1.0 every bar (TargetPercent semantics)
        call leg      = -1.0 on write bars, +1.0 on close bars,
                        0.0 elsewhere (Amount semantics)
        other columns = 0.0
Mode 2 (buy-and-hold approximation, benchmark runner fallback):
    prices columns ⊇ [underlying_symbol]
    weights:
        underlying    = +1.0 every bar
        other columns = 0.0

Synthetic-options adapter integration
-------------------------------------
The synthetic call-leg premium series is built by
:meth:`make_call_leg_prices`, which:

1. Walks the underlying-price index, identifying the first trading
   day of each calendar month as a *write date*.
2. For each write date, calls
   ``chain_feed.fetch_chain(underlying_symbol, write_date)`` and
   selects the call quote with the smallest strike ≥ ``spot * (1 +
   otm_pct)`` whose expiry clears a 25-day-DTE floor.
3. The selected call's premium is BS-priced at write, and re-priced
   each in-position bar via :func:`alphakit.data.options.bs.call_price`
   using the current spot, the fixed strike, the decreasing
   time-to-expiry, the risk-free rate, and the chain's per-expiry
   IV (held constant within the position).
4. At expiry, the leg's price drops to intrinsic
   (``max(0, S_T − K)``); on the bar(s) between expiry and the
   next write date the leg's price is 0 (no position held); at
   the next write date a fresh call is written and the price
   jumps to the new BS premium.

The output is a ``pd.Series`` aligned to the underlying's index,
ready to be appended as a new column on the ``prices`` DataFrame
fed to the strategy. The strategy's :meth:`generate_signals`
detects write and close events from the leg's price series via
zero-to-positive and positive-to-zero discontinuity detection.

Methodology deviations from the published BXM construction
----------------------------------------------------------
* **Synthetic chain has flat IV across strikes** (no skew) — see
  ``docs/feeds/synthetic-options.md``. The 2 % OTM call is priced
  at the same IV as the ATM call, so the strategy captures none
  of the *skew*-decomposition of the put-call-parity-equivalent
  short put. Real-feed verification is deferred to Phase 3 with
  Polygon (ADR-004).
* **No bid-ask spread / financing model.** The synthetic chain
  has ``bid == ask == last``. Real-world covered-call writes lose
  a documented 0.5-1 % per year to bid-ask in retail-style
  execution; the synthetic backtest does not reflect this.
* **Calendar-month-start writes vs. third-Friday writes.** The
  exact BXM index rolls on the third Friday; this strategy uses
  the first trading day of the calendar month for tractability.
* **OTM-expiry close approximation.** When the call expires
  out-of-the-money the make_call_leg_prices logic sets the
  expiry-bar price to 0 (intrinsic = 0). The
  zero-discontinuity-based close detection then fires on the
  bar *before* the expiry bar at a small residual time-value
  premium. The resulting per-cycle P&L is approximately 1-2 %
  short of the analytic premium-minus-zero-intrinsic — within
  the substrate-noise tolerance documented in
  ``known_failures.md``.

Edge cases
----------
* Empty input → empty weights frame.
* Missing underlying column → ``KeyError``.
* Non-DataFrame / non-DatetimeIndex input → ``TypeError``.
* Non-positive prices for the underlying → ``ValueError``.
* :meth:`make_call_leg_prices` requires at least one full month of
  underlying history before its first write date (the synthetic
  chain itself needs ≥252 bars to compute realized vol).
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

# Trading-days-per-year for time-to-expiry conversion in the
# call-leg evolution. The BS pricer takes T in year-fractions; we
# use 365.0 calendar days for consistency with the synthetic-options
# adapter (which builds quotes with ``T = (expiry - as_of).days /
# 365.0``).
_DAYS_PER_YEAR: float = 365.0

# Floor used by ``make_call_leg_prices`` for bars between the close
# of one position and the open of the next. vectorbt's ``Portfolio``
# constructor (with ``cash_sharing=True`` and ``group_by=True``)
# computes a per-bar mark-to-market valuation across every column
# and rejects non-positive prices on any bar — even bars where the
# strategy emits no trade. The flat-bar floor satisfies that
# constraint while staying well below the lifecycle-detection
# epsilon below.
_LEG_FLAT_FLOOR: float = 1e-6

# Lower bound used to detect "position open" bars when reading back
# the call-leg price series in :meth:`generate_signals`. Anything
# above this threshold is treated as in-position; anything at or
# below as flat (post-close before next write, or pre-warmup). The
# threshold is set well above ``_LEG_FLAT_FLOOR`` so the floor never
# registers as an open position.
_LEG_PRICE_EPSILON: float = 1e-3


def _to_date(d: date | datetime | pd.Timestamp) -> date:
    """Normalise any date-like to a :class:`datetime.date`."""
    if isinstance(d, pd.Timestamp):
        return d.date()
    if isinstance(d, datetime):
        return d.date()
    return d


def _is_first_trading_day_of_month(idx: pd.DatetimeIndex) -> np.ndarray:
    """Mark the first bar of each calendar month in a daily index."""
    months = idx.to_period("M")
    is_first = np.zeros(len(idx), dtype=bool)
    is_first[0] = True
    is_first[1:] = months[1:] != months[:-1]
    return is_first


class CoveredCallSystematic:
    """Single-leg systematic 1-month 2 % OTM call write on synthetic chains.

    Parameters
    ----------
    underlying_symbol
        Column name for the underlying equity / index in the
        ``prices`` DataFrame. Defaults to ``"SPY"``.
    otm_pct
        Out-of-the-money offset for the written call, expressed as
        a decimal fraction (``0.02`` for 2 % OTM). Must be ≥ 0
        and ≤ 0.50. ``0.0`` is the exactly-ATM case used by
        ``bxm_replication``.
    chain_feed
        Optional explicit feed object for chain access. When ``None``
        (default), the strategy resolves
        ``FeedRegistry.get("synthetic-options")`` lazily — same
        pattern :class:`SyntheticOptionsFeed` itself uses for its
        underlying feed.
    """

    name: str = "covered_call_systematic"
    family: str = "options"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.2469/faj.v70.n6.5"  # Israelov-Nielsen 2014 (primary)
    rebalance_frequency: str = "monthly"

    # ``discrete_legs`` is set in __init__ because it depends on the
    # instance-specific call_leg_symbol (which encodes ``otm_pct``).
    # Class-level type annotation only; the bridge accesses this via
    # :func:`alphakit.core.protocols.get_discrete_legs` which uses
    # ``getattr(strategy, "discrete_legs", ())`` so legacy strategies
    # remain unaffected.
    discrete_legs: tuple[str, ...]

    def __init__(
        self,
        *,
        underlying_symbol: str = "SPY",
        otm_pct: float = 0.02,
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
        # Instance-level discrete_legs reflects the actual leg name
        # this instance will produce via make_call_leg_prices.
        self.discrete_legs = (self.call_leg_symbol,)

    @property
    def chain_feed(self) -> DataFeedProtocol:
        """Resolve the chain-providing feed lazily.

        Mirrors :class:`SyntheticOptionsFeed.underlying_feed` — the
        explicit constructor argument wins; otherwise the registry
        is queried at access time. Lazy resolution avoids an import-
        ordering hazard between this strategy and the synthetic
        adapter.
        """
        if self._chain_feed is not None:
            return self._chain_feed
        return FeedRegistry.get("synthetic-options")

    @property
    def call_leg_symbol(self) -> str:
        """Synthetic short-call leg column name.

        Format: ``f"{underlying}_CALL_OTM{round(otm_pct*100):02d}PCT_M1"`` —
        e.g. ``"SPY_CALL_OTM02PCT_M1"`` for the 2 % OTM 1-month call
        on SPY. Stable across strategy invocations so users can
        construct the call-leg column once and reuse it.
        """
        pct = round(self.otm_pct * 100)
        return f"{self.underlying_symbol}_CALL_OTM{pct:02d}PCT_M1"

    def make_call_leg_prices(
        self,
        underlying_prices: pd.Series,
        *,
        chain_feed: DataFeedProtocol | None = None,
    ) -> pd.Series:
        """Construct the synthetic short-call premium series.

        For each first-trading-day-of-month write date in
        ``underlying_prices.index``, fetch the option chain, select
        the closest call with strike ≥ ``spot * (1 + otm_pct)`` and
        with the first chain expiry clearing a 25-day-DTE floor, and
        forward-evolve the call premium daily via Black-Scholes
        (current spot, fixed strike, decreasing TTE, chain risk-free
        rate, chain IV held constant within the position). At expiry
        the leg's price is set to intrinsic (``max(0, S_T − K)``)
        and falls to 0 between expiry and the next write date.

        Parameters
        ----------
        underlying_prices
            Underlying close-price series indexed by trading-day
            timestamps.
        chain_feed
            Optional override for the chain provider. Falls back to
            :attr:`chain_feed` when ``None``.

        Returns
        -------
        pd.Series
            Index aligned to ``underlying_prices``. Values are call
            premia (≥ 0). Days before the first write date and days
            between expiry and the next write date are 0.0.
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
            return pd.Series(dtype=float, name=self.call_leg_symbol)

        feed = chain_feed if chain_feed is not None else self.chain_feed
        idx = underlying_prices.index
        prices_arr = underlying_prices.to_numpy(dtype=float)
        write_mask = _is_first_trading_day_of_month(idx)

        # State: current open call position (strike, expiry, sigma)
        current_strike: float | None = None
        current_expiry: date | None = None
        current_sigma: float | None = None
        # Initialise the premium array at the flat floor — bars without
        # an open position get a tiny positive sentinel value so the
        # bridge's mark-to-market doesn't reject them. In-position bars
        # are overwritten with the BS-priced premium below.
        premium = np.full(len(idx), _LEG_FLAT_FLOOR, dtype=float)

        for i in range(len(idx)):
            today = _to_date(idx[i])
            spot = prices_arr[i]

            # Close at expiry: the call premium becomes intrinsic
            # value on the expiry day, then position is flat until
            # the next write date. Floored at ``_LEG_FLAT_FLOOR`` so
            # the bridge's mark-to-market never sees a non-positive
            # price (even for OTM expiries where intrinsic = 0).
            if current_expiry is not None and today >= current_expiry:
                premium[i] = max(_LEG_FLAT_FLOOR, spot - cast(float, current_strike))
                current_strike = None
                current_expiry = None
                current_sigma = None
                # If the expiry day also happens to be a write date,
                # fall through to the write block.

            # Write date: open a new short-call position.
            if write_mask[i] and current_expiry is None:
                try:
                    chain = feed.fetch_chain(self.underlying_symbol, idx[i].to_pydatetime())
                except (ValueError, NotImplementedError):
                    # Insufficient history or chain-not-supported —
                    # leave premium at the flat floor for this bar;
                    # try again next write date.
                    continue
                strike, expiry, sigma = self._select_call(chain, spot)
                if strike is None or expiry is None or sigma is None:
                    continue
                current_strike = strike
                current_expiry = expiry
                current_sigma = sigma
                # Initial premium: BS-priced at the chain's IV.
                tte = (current_expiry - today).days / _DAYS_PER_YEAR
                if tte > 0:
                    premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.call_price(
                            spot,
                            current_strike,
                            tte,
                            _DEFAULT_RISK_FREE_RATE,
                            current_sigma,
                        ),
                    )
                continue

            # Daily mark-to-market between write and expiry.
            if current_strike is not None and current_expiry is not None:
                tte = (current_expiry - today).days / _DAYS_PER_YEAR
                if tte > 0:
                    premium[i] = max(
                        _LEG_FLAT_FLOOR,
                        bs.call_price(
                            spot,
                            current_strike,
                            tte,
                            _DEFAULT_RISK_FREE_RATE,
                            cast(float, current_sigma),
                        ),
                    )
                else:
                    premium[i] = max(_LEG_FLAT_FLOOR, spot - current_strike)

        return pd.Series(premium, index=underlying_prices.index, name=self.call_leg_symbol)

    def _select_call(
        self,
        chain: OptionChain,
        spot: float,
    ) -> tuple[float | None, date | None, float | None]:
        """Pick the (strike, expiry, sigma) for the new write.

        * Expiry: first chain expiry strictly past 25 days from the
          chain's ``as_of``, falling back to the latest available
          expiry if the chain is too short-dated. The synthetic-
          options adapter exposes 11-14 expiries spanning weekly +
          monthly + quarterly third-Fridays; the next monthly third-
          Friday after the write date is the natural target.
        * Strike: the smallest strike ≥ spot × (1 + otm_pct) that
          exists on the chain. If no strike clears the threshold
          (extreme rally past the 1.20× upper grid bound), falls
          back to the largest available strike.
        """
        target_strike = spot * (1.0 + self.otm_pct)
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

        calls = chain.filter(expiry=expiry, right=OptionRight.CALL)
        if not calls:
            return None, None, None
        otm_calls = [q for q in calls if q.strike >= target_strike]
        if otm_calls:
            otm_calls.sort(key=lambda q: q.strike)
            chosen = otm_calls[0]
        else:
            chosen = max(calls, key=lambda q: q.strike)
        sigma = chosen.iv if chosen.iv is not None and chosen.iv > 0 else None
        return chosen.strike, expiry, sigma

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a covered-call weights DataFrame.

        See module docstring for the full mode behaviour. In short:

        * Both ``underlying_symbol`` and :attr:`call_leg_symbol`
          present → 2-column weights:
              underlying = +1.0 every bar (TargetPercent)
              call leg   = -1.0 on writes, +1.0 on closes, 0.0
                           otherwise (Amount via discrete_legs)
        * Only ``underlying_symbol`` present → 1-column weights
          (+1.0, buy-and-hold approximation; benchmark-runner mode).

        Write and close events on the call leg are detected from
        the leg's price series via zero-to-positive and
        positive-to-zero discontinuities. This requires no
        additional input beyond the ``prices`` DataFrame —
        :meth:`make_call_leg_prices` embeds the lifecycle in the
        price series and :meth:`generate_signals` reads it back.
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
        if self.call_leg_symbol in prices.columns:
            leg = prices[self.call_leg_symbol].to_numpy(dtype=float)
            write_mask, close_mask = _detect_lifecycle_events(leg)
            weights.loc[prices.index[write_mask], self.call_leg_symbol] = -1.0
            weights.loc[prices.index[close_mask], self.call_leg_symbol] = 1.0
        return weights


def _detect_lifecycle_events(leg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Detect write/close events from a call-leg price series.

    Write event at bar i: ``leg[i] > epsilon`` AND
    (``i == 0`` OR ``leg[i-1] <= epsilon``). The leg's price has
    just transitioned from "no position" (the 1e-6 flat floor) to
    "position open" (BS-priced premium ≥ 1e-3).

    Close event at bar i: ``leg[i] > epsilon`` AND
    (``i == n-1`` OR ``leg[i+1] <= epsilon``). The leg's price is
    about to drop to the flat floor (post-expiry).

    These two masks together encode the discrete-trade lifecycle
    that the bridge consumes via ``Amount`` semantics: -1 on
    writes opens a one-contract short, +1 on closes flattens it.

    The OTM-expiry edge case (intrinsic = 0 at the expiry bar
    itself, floored to 1e-6) means the close fires on the bar
    *before* the expiry bar at a small residual time-value premium
    rather than on the expiry bar at exactly zero. The resulting
    per-cycle P&L is approximately 1-2 % short of the analytic
    premium-minus-zero-intrinsic — within the substrate-noise
    tolerance documented in ``known_failures.md``.
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


# Lazy registration — the synthetic-options feed must be importable
# at strategy-class-definition time even though we resolve it lazily
# inside ``chain_feed``. Importing the synthetic adapter here is what
# triggers the feed's at-import registration so that
# ``FeedRegistry.get("synthetic-options")`` succeeds.
with contextlib.suppress(ImportError):
    from alphakit.data.options import synthetic as _synthetic  # noqa: F401
