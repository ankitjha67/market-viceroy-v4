"""CBOE BXMP-aligned monthly call + put overlay on synthetic chains.

This is the **reframe** of the practitioner "wheel" strategy under
the Phase 2 honesty framework — see
``docs/phase-2-amendments.md`` 2026-05-01 entry "reframe
wheel_strategy → bxmp_overlay". The "wheel" sequences put writes
and call writes based on assignment state (folklore mechanic with
no peer-reviewed citation); BXMP is its academic counterpart,
combining the BXM and PUT index methodologies *simultaneously*
each month rather than alternating.

Foundational paper
------------------
Whaley, R. E. (2002). *Return and Risk of CBOE Buy Write Monthly
Index*. Journal of Derivatives, 10(2), 35-42.
https://doi.org/10.3905/jod.2002.319188

The CBOE BXMP index combines the ATM call write rule of BXM
(Whaley 2002) with the cash-secured put write rule of PUT (also
Whaley methodology). Each month: long underlying, short ATM call,
short OTM put with cash collateral.

Primary methodology
-------------------
Israelov, R. & Nielsen, L. N. (2014). *Covered Call Strategies:
One Fact and Eight Myths*. Financial Analysts Journal, 70(6), 23-31.
https://doi.org/10.2469/faj.v70.n6.5

Israelov-Nielsen's three-factor decomposition (equity beta + short
volatility + implicit short put) generalises straightforwardly to
the BXMP combined book: the put-call-parity equivalence makes
BXMP a 2× short-volatility / 1× equity-beta exposure on a single
underlying.

Differentiation from `wheel_strategy` folklore
----------------------------------------------
The "wheel" runs a state machine: write CSP → if assigned, hold
underlying and write covered call → if assigned again, restart at
CSP. BXMP simply writes both each month against the underlying
position, with no path-conditional state. The two strategies'
*economic content* is similar (alternating short-put and short-call
exposure on a single underlying) but BXMP's deterministic monthly
construction makes it a citable systematic strategy whereas the
wheel's assignment-conditional sequencing has no peer-reviewed
anchor.

Implementation
--------------
Composition wrapper combining
:class:`~alphakit.strategies.options.covered_call_systematic.strategy.CoveredCallSystematic`
(default ``otm_pct = 0.0`` per BXM canonical rule) with
:class:`~alphakit.strategies.options.cash_secured_put_systematic.strategy.CashSecuredPutSystematic`
(default ``otm_pct = 0.05`` per PUT-aligned practitioner default).

Output convention (Mode 1, three-instrument book):

    prices columns ⊇ [underlying, call_leg, put_leg]
    weights:
        underlying = +1.0 every bar (TargetPercent)
        call leg   = -1 / +1 lifecycle from CoveredCallSystematic
                     (Amount via discrete_legs)
        put leg    = -1 / +1 lifecycle from CashSecuredPutSystematic
                     (Amount via discrete_legs)

Mode 2 fallback (single-column underlying-only) and Mode 1.5
(underlying + one of the two legs) degrade gracefully — the
discrete_legs dispatch silently filters declared-but-absent legs
per the bridge's Mode-2-fallback policy.

The strategy declares ``discrete_legs = (call_leg_symbol,
put_leg_symbol)`` so the bridge dispatches ``SizeType.Amount`` for
both option legs and ``SizeType.TargetPercent`` for the underlying.

Cluster expectations
--------------------
* vs ``covered_call_systematic`` (ρ ≈ 0.85-0.95): BXMP includes
  the call write and adds the put leg.
* vs ``cash_secured_put_systematic`` (ρ ≈ 0.85-0.95): BXMP
  includes the put write and adds the call leg.
* vs ``bxm_replication`` (ρ ≈ 0.85-0.95): BXMP shares the ATM
  call rule, adds the put.
* vs ``short_strangle_monthly`` (Commit 7): ρ ≈ 0.80-0.90.
  Same combined short-vol exposure with different leg construction
  (short-strangle is a 2-leg trade with both legs OTM; BXMP is a
  3-instrument book with the underlying as the third).

Documented in ``known_failures.md``.
"""

from __future__ import annotations

import pandas as pd
from alphakit.core.protocols import DataFeedProtocol
from alphakit.strategies.options.cash_secured_put_systematic.strategy import (
    CashSecuredPutSystematic,
)
from alphakit.strategies.options.covered_call_systematic.strategy import (
    CoveredCallSystematic,
)


class BXMPOverlay:
    """CBOE BXMP overlay: monthly ATM-call write + 5 %-OTM-put write.

    Parameters
    ----------
    underlying_symbol
        Column name for the underlying. Defaults to ``"SPY"``.
    call_otm_pct
        OTM offset for the call write (decimal). Defaults to ``0.0``
        per the BXM canonical ATM rule.
    put_otm_pct
        OTM offset for the put write (decimal). Defaults to ``0.05``
        per the PUT-aligned practitioner default.
    chain_feed
        Optional explicit feed object. When ``None`` (default),
        resolves ``FeedRegistry.get("synthetic-options")`` lazily.
    """

    name: str = "bxmp_overlay"
    family: str = "options"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.2469/faj.v70.n6.5"  # Israelov-Nielsen 2014 (primary)
    rebalance_frequency: str = "monthly"

    discrete_legs: tuple[str, ...]

    def __init__(
        self,
        *,
        underlying_symbol: str = "SPY",
        call_otm_pct: float = 0.0,
        put_otm_pct: float = 0.05,
        chain_feed: DataFeedProtocol | None = None,
    ) -> None:
        if not underlying_symbol:
            raise ValueError("underlying_symbol must be a non-empty string")
        self._call_strategy = CoveredCallSystematic(
            underlying_symbol=underlying_symbol,
            otm_pct=call_otm_pct,
            chain_feed=chain_feed,
        )
        self._put_strategy = CashSecuredPutSystematic(
            underlying_symbol=underlying_symbol,
            otm_pct=put_otm_pct,
            chain_feed=chain_feed,
        )
        self.underlying_symbol = underlying_symbol
        self.call_otm_pct = call_otm_pct
        self.put_otm_pct = put_otm_pct
        self.discrete_legs = (self.call_leg_symbol, self.put_leg_symbol)

    @property
    def chain_feed(self) -> DataFeedProtocol:
        return self._call_strategy.chain_feed

    @property
    def call_leg_symbol(self) -> str:
        return self._call_strategy.call_leg_symbol

    @property
    def put_leg_symbol(self) -> str:
        return self._put_strategy.put_leg_symbol

    def make_call_leg_prices(
        self,
        underlying_prices: pd.Series,
        *,
        chain_feed: DataFeedProtocol | None = None,
    ) -> pd.Series:
        """Delegate to the inner ``CoveredCallSystematic``."""
        return self._call_strategy.make_call_leg_prices(underlying_prices, chain_feed=chain_feed)

    def make_put_leg_prices(
        self,
        underlying_prices: pd.Series,
        *,
        chain_feed: DataFeedProtocol | None = None,
    ) -> pd.Series:
        """Delegate to the inner ``CashSecuredPutSystematic``."""
        return self._put_strategy.make_put_leg_prices(underlying_prices, chain_feed=chain_feed)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return the combined BXMP weights DataFrame.

        Mode 1 (full BXMP overlay):
            underlying = +1.0 every bar (TargetPercent)
            call leg   = -1 on writes, +1 on closes (Amount)
            put leg    = -1 on writes, +1 on closes (Amount)
            other      = 0
        Mode 2 (underlying-only fallback):
            underlying = +1.0 every bar
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

        # Each inner strategy emits its own underlying = +1.0 in
        # weights, but we only want *one* +1.0 on the shared
        # underlying. We extract the call-leg and put-leg columns
        # from each inner strategy's output and merge into our
        # combined weights frame; the underlying column is set
        # above and not overwritten.
        if self.call_leg_symbol in prices.columns:
            cc_weights = self._call_strategy.generate_signals(prices)
            weights[self.call_leg_symbol] = cc_weights[self.call_leg_symbol]
        if self.put_leg_symbol in prices.columns:
            csp_weights = self._put_strategy.generate_signals(prices)
            weights[self.put_leg_symbol] = csp_weights[self.put_leg_symbol]
        return weights
