"""2-leg short-volatility monthly strangle write on synthetic chains.

Foundational paper
------------------
Coval, J. D. & Shumway, T. (2001). *Expected option returns*.
Journal of Finance, 56(3), 983-1009.
https://doi.org/10.1111/0022-1082.00352

Coval & Shumway document the *negative expected returns* of long
straddles (and equivalently the *positive expected returns* of
short straddles / strangles) — the empirical foundation for
selling-volatility strategies. The negative expected return on
long-volatility positions is the variance risk premium that
short-strangle writers harvest.

Primary methodology
-------------------
Bondarenko, O. (2014). *Why Are Put Options So Expensive?*.
Quarterly Journal of Finance, 4(1), 1450015.
https://doi.org/10.1142/S2010139214500050

Bondarenko quantifies the variance risk premium across S&P 500
puts and calls and documents the systematic short-volatility
premium that strangles harvest. The 10 % OTM strangle write is
the canonical Bondarenko setup: deep enough OTM that the
short-strikes typically expire worthless (collecting full
premium), wide enough that random-walk realisations don't
breach in most months.

Differentiation from siblings
-----------------------------
Iron condor minus the protective wings: same short-vol exposure
(short OTM put + short OTM call) but with **uncapped tails** in
both directions. The trade-off:

* Higher net premium per cycle (no wing-cost drag).
* Uncapped maximum loss per cycle when realised vol breaks
  through either strike.

Cluster expectations:

* vs ``iron_condor_monthly`` (Commit 6): ρ ≈ 0.85-0.95.
  Same short-vol exposure with iron condor's protective
  wings.
* vs ``bxmp_overlay`` (Commit 5): ρ ≈ 0.80-0.90.
  Same combined call+put short-vol with BXMP's underlying
  long position.
* vs ``covered_call_systematic`` (Commit 2): ρ ≈ 0.70-0.85.
  Strangle captures both call and put VRP; covered call
  captures only the call side and adds equity beta.
* vs ``cash_secured_put_systematic`` (Commit 3): ρ ≈ 0.70-0.85.
  Strangle captures both sides; CSP captures only the put side
  with implicit equity exposure.

Bridge integration: 2 discrete legs
-----------------------------------
Same dispatch pattern as ``iron_condor_monthly`` minus the
wings. Strategy declares ``discrete_legs = (short_put_leg,
short_call_leg)``; the bridge applies ``SizeType.Amount``
semantics to both, ``SizeType.TargetPercent`` (default) to the
underlying — but the strangle emits ``0.0`` weight on the
underlying because it's a pure-options trade.

Implementation
--------------
Composition wrapper using two inner strategies:

* ``CashSecuredPutSystematic(otm_pct=put_otm)`` for the short
  put leg.
* ``CoveredCallSystematic(otm_pct=call_otm)`` for the short
  call leg.

Each inner ``make_*_leg_prices`` builds the leg's premium
series; ``generate_signals`` reads each leg's lifecycle from
zero-to-positive (write) and positive-to-zero (close)
discontinuities and emits ``-1`` at write / ``+1`` at close
(short-side convention) for both legs.

The 2 inner strategies share the same write/expiry calendar
because they use the same chain and the same underlying-price
index — lifecycles synchronise automatically.

Documented in ``known_failures.md``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from alphakit.core.protocols import DataFeedProtocol
from alphakit.strategies.options.cash_secured_put_systematic.strategy import (
    CashSecuredPutSystematic,
)
from alphakit.strategies.options.covered_call_systematic.strategy import (
    CoveredCallSystematic,
)

_LEG_PRICE_EPSILON: float = 1e-3


class ShortStrangleMonthly:
    """2-leg short-volatility monthly strangle write.

    Parameters
    ----------
    underlying_symbol
        Column name for the underlying. Defaults to ``"SPY"``. The
        strangle is a pure-options trade — no underlying weight is
        emitted — but the column must be present in ``prices``.
    put_otm
        OTM offset for the short put leg. Defaults to ``0.10``.
    call_otm
        OTM offset for the short call leg. Defaults to ``0.10``.
    chain_feed
        Optional explicit feed object.
    """

    name: str = "short_strangle_monthly"
    family: str = "options"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1142/S2010139214500050"  # Bondarenko 2014 (primary)
    rebalance_frequency: str = "monthly"

    discrete_legs: tuple[str, ...]

    def __init__(
        self,
        *,
        underlying_symbol: str = "SPY",
        put_otm: float = 0.10,
        call_otm: float = 0.10,
        chain_feed: DataFeedProtocol | None = None,
    ) -> None:
        if not underlying_symbol:
            raise ValueError("underlying_symbol must be a non-empty string")
        self.underlying_symbol = underlying_symbol
        self.put_otm = put_otm
        self.call_otm = call_otm

        self._short_put = CashSecuredPutSystematic(
            underlying_symbol=underlying_symbol,
            otm_pct=put_otm,
            chain_feed=chain_feed,
        )
        self._short_call = CoveredCallSystematic(
            underlying_symbol=underlying_symbol,
            otm_pct=call_otm,
            chain_feed=chain_feed,
        )
        self.discrete_legs = (self.put_leg_symbol, self.call_leg_symbol)

    @property
    def chain_feed(self) -> DataFeedProtocol:
        return self._short_put.chain_feed

    @property
    def put_leg_symbol(self) -> str:
        return self._short_put.put_leg_symbol

    @property
    def call_leg_symbol(self) -> str:
        return self._short_call.call_leg_symbol

    def make_legs_prices(
        self,
        underlying_prices: pd.Series,
        *,
        chain_feed: DataFeedProtocol | None = None,
    ) -> pd.DataFrame:
        """Construct the 2-leg premium DataFrame in one call.

        Returns a DataFrame indexed like ``underlying_prices`` with
        2 columns: short-put leg, short-call leg.
        """
        sp = self._short_put.make_put_leg_prices(underlying_prices, chain_feed=chain_feed)
        sc = self._short_call.make_call_leg_prices(underlying_prices, chain_feed=chain_feed)
        return pd.DataFrame(
            {self.put_leg_symbol: sp, self.call_leg_symbol: sc},
            index=underlying_prices.index,
        )

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return the 2-leg short-strangle weights DataFrame.

        Mode 1 (full strangle):
            underlying = 0.0 (pure-options trade)
            put leg    = -1 on writes, +1 on closes (Amount, short)
            call leg   = -1 on writes, +1 on closes (Amount, short)
        Mode 2 (degenerate underlying-only):
            all weights = 0 (no trade — strangle needs both legs)
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
        # Pure-options trade — underlying weight 0.

        # Both legs are SHORT: -1 at write, +1 at close.
        for leg_col in (self.put_leg_symbol, self.call_leg_symbol):
            if leg_col not in prices.columns:
                continue
            leg = prices[leg_col].to_numpy(dtype=float)
            write_mask, close_mask = _detect_lifecycle_events(leg)
            weights.loc[prices.index[write_mask], leg_col] = -1.0
            weights.loc[prices.index[close_mask], leg_col] = 1.0
        return weights


def _detect_lifecycle_events(leg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Detect write/close events on a leg's price series.

    Same algorithm as covered_call_systematic / iron_condor_monthly.
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
