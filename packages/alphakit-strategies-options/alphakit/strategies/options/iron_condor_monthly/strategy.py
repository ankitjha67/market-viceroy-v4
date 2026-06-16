"""4-leg defined-risk short-volatility monthly iron-condor write.

Foundational paper
------------------
Hill, J. M., Balasubramanian, V., Gregory, K. & Tierens, I. (2006).
*Finding alpha via covered index writing*. Journal of Derivatives,
13(3), 51-65. https://doi.org/10.3905/jod.2006.622777

Hill et al. survey systematic option-overlay strategies on the
S&P 500, including the iron-condor structure as a defined-risk
short-volatility variant of the BXM/PUT family. The paper
documents the systematic-write payoff decomposition that the
iron condor inherits with the addition of protective wings.

Primary methodology
-------------------
CBOE CNDR (Iron Condor Index) construction methodology document.
The CNDR index sells one OTM call + one OTM put each month and
buys further-OTM call + further-OTM put as protective wings,
all on the S&P 500 with deterministic monthly roll. Wing widths
are calibrated to the index spec (typically 5 % short-strike
offset + 10 % long-strike offset).

The synthetic chain's 5 %-spaced strike grid (``0.80, 0.85, …,
1.20`` × spot per ADR-005) maps cleanly to these CNDR strikes:
short-put at 0.95×, long-put at 0.90×, short-call at 1.05×,
long-call at 1.10×. All four sit on the synthetic chain's grid
points exactly.

Strategy structure (4-leg)
--------------------------
For each first trading day of a calendar month:

* **Short put** at ``spot × (1 - short_put_otm)`` (e.g. 5 % OTM)
* **Long put** at ``spot × (1 - long_put_otm)`` (e.g. 10 % OTM,
  protective wing)
* **Short call** at ``spot × (1 + short_call_otm)`` (e.g. 5 % OTM)
* **Long call** at ``spot × (1 + long_call_otm)`` (e.g. 10 % OTM,
  protective wing)

Net premium received = (short put premium + short call premium)
− (long put premium + long call premium). Maximum loss per
contract = wing width − net premium = (long put strike − short
put strike) or (long call strike − short call strike), whichever
the underlying breaches at expiry.

Bridge integration: 4 discrete legs
-----------------------------------
This strategy declares ``discrete_legs`` containing **four**
leg symbols (short put, long put, short call, long call). The
``vectorbt_bridge`` dispatches ``SizeType.Amount`` to all four;
the underlying gets ``SizeType.TargetPercent`` (default), but
the iron condor is a *pure-options trade with no underlying
position* — so the strategy emits ``0.0`` weight on the
underlying column. The underlying column's price series is still
required by the bridge's mark-to-market (cash-sharing context),
hence the strategy still requires the underlying to be present
in ``prices``, even though it doesn't trade it.

Implementation
--------------
Composition wrapper using four inner strategies:

* ``CashSecuredPutSystematic(otm_pct=short_put_otm)`` for the
  short-put leg (sign +1 for short, applied at write/close).
* ``CashSecuredPutSystematic(otm_pct=long_put_otm)`` for the
  long-put leg (sign −1 for long, applied at write/close).
* ``CoveredCallSystematic(otm_pct=short_call_otm)`` for the
  short-call leg.
* ``CoveredCallSystematic(otm_pct=long_call_otm)`` for the
  long-call leg.

Each inner strategy's ``make_*_leg_prices`` builds the leg's
premium series; ``generate_signals`` reads each leg's
zero-to-positive (write) and positive-to-zero (close)
discontinuities and emits the appropriate signed weight (-1 for
short legs, +1 for long legs at write; opposite at close).

The 4 inner strategies share the same write/expiry calendar
because they all use the same ``chain_feed`` and the same
underlying-price index — every chain fetch happens on the same
write date with the same expiry rule, so the lifecycles
synchronise automatically.

Cluster expectations
--------------------
* vs ``short_strangle_monthly`` (Commit 7): ρ ≈ 0.85-0.95.
  Short strangle is iron condor without protective wings;
  same short-vol exposure, more left + right tail.
* vs ``covered_call_systematic`` (Commit 2): ρ ≈ 0.50-0.70.
  Capped vs uncapped short-vol on the call side.
* vs ``cash_secured_put_systematic`` (Commit 3): ρ ≈ 0.50-0.70.
  Capped vs uncapped short-vol on the put side.
* vs ``bxmp_overlay`` (Commit 5): ρ ≈ 0.55-0.75. BXMP carries
  equity beta + 2× uncapped short vol; iron condor is pure
  capped short vol with no equity beta.

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

# Lifecycle-detection epsilon — same convention as
# covered_call_systematic / cash_secured_put_systematic. Bars with
# leg price > epsilon are "in-position"; ≤ epsilon are flat.
_LEG_PRICE_EPSILON: float = 1e-3


class IronCondorMonthly:
    """4-leg defined-risk short-volatility monthly iron-condor write.

    Parameters
    ----------
    underlying_symbol
        Column name for the underlying. Defaults to ``"SPY"``. The
        iron condor is a pure-options trade — no underlying weight
        is emitted — but the column must be present in ``prices``
        for the bridge's mark-to-market context.
    short_put_otm
        OTM offset for the short-put leg. Defaults to ``0.05``.
    long_put_otm
        OTM offset for the long-put protective wing. Defaults to
        ``0.10``. Must be > ``short_put_otm`` (deeper-OTM
        protection).
    short_call_otm
        OTM offset for the short-call leg. Defaults to ``0.05``.
    long_call_otm
        OTM offset for the long-call protective wing. Defaults to
        ``0.10``. Must be > ``short_call_otm``.
    chain_feed
        Optional explicit feed object.
    """

    name: str = "iron_condor_monthly"
    family: str = "options"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.3905/jod.2006.622777"  # Hill et al. 2006
    rebalance_frequency: str = "monthly"

    discrete_legs: tuple[str, ...]

    def __init__(
        self,
        *,
        underlying_symbol: str = "SPY",
        short_put_otm: float = 0.05,
        long_put_otm: float = 0.10,
        short_call_otm: float = 0.05,
        long_call_otm: float = 0.10,
        chain_feed: DataFeedProtocol | None = None,
    ) -> None:
        if not underlying_symbol:
            raise ValueError("underlying_symbol must be a non-empty string")
        if long_put_otm <= short_put_otm:
            raise ValueError(
                f"long_put_otm ({long_put_otm}) must be > short_put_otm "
                f"({short_put_otm}) — long puts protect at deeper OTM"
            )
        if long_call_otm <= short_call_otm:
            raise ValueError(
                f"long_call_otm ({long_call_otm}) must be > short_call_otm "
                f"({short_call_otm}) — long calls protect at deeper OTM"
            )

        self.underlying_symbol = underlying_symbol
        self.short_put_otm = short_put_otm
        self.long_put_otm = long_put_otm
        self.short_call_otm = short_call_otm
        self.long_call_otm = long_call_otm

        # Four inner strategies, each producing one leg's premium
        # series at its own strike.
        self._short_put = CashSecuredPutSystematic(
            underlying_symbol=underlying_symbol,
            otm_pct=short_put_otm,
            chain_feed=chain_feed,
        )
        self._long_put = CashSecuredPutSystematic(
            underlying_symbol=underlying_symbol,
            otm_pct=long_put_otm,
            chain_feed=chain_feed,
        )
        self._short_call = CoveredCallSystematic(
            underlying_symbol=underlying_symbol,
            otm_pct=short_call_otm,
            chain_feed=chain_feed,
        )
        self._long_call = CoveredCallSystematic(
            underlying_symbol=underlying_symbol,
            otm_pct=long_call_otm,
            chain_feed=chain_feed,
        )

        self.discrete_legs = (
            self.short_put_leg_symbol,
            self.long_put_leg_symbol,
            self.short_call_leg_symbol,
            self.long_call_leg_symbol,
        )

    @property
    def chain_feed(self) -> DataFeedProtocol:
        return self._short_put.chain_feed

    @property
    def short_put_leg_symbol(self) -> str:
        return self._short_put.put_leg_symbol

    @property
    def long_put_leg_symbol(self) -> str:
        return self._long_put.put_leg_symbol

    @property
    def short_call_leg_symbol(self) -> str:
        return self._short_call.call_leg_symbol

    @property
    def long_call_leg_symbol(self) -> str:
        return self._long_call.call_leg_symbol

    def make_legs_prices(
        self,
        underlying_prices: pd.Series,
        *,
        chain_feed: DataFeedProtocol | None = None,
    ) -> pd.DataFrame:
        """Construct all 4 leg-premium series in one call.

        Returns a DataFrame indexed like ``underlying_prices`` with
        4 columns: short-put, long-put, short-call, long-call leg
        symbols. Each column is the BS-priced premium evolution for
        that leg over the monthly write/expiry cycles.
        """
        sp = self._short_put.make_put_leg_prices(underlying_prices, chain_feed=chain_feed)
        lp = self._long_put.make_put_leg_prices(underlying_prices, chain_feed=chain_feed)
        sc = self._short_call.make_call_leg_prices(underlying_prices, chain_feed=chain_feed)
        lc = self._long_call.make_call_leg_prices(underlying_prices, chain_feed=chain_feed)
        return pd.DataFrame(
            {
                self.short_put_leg_symbol: sp,
                self.long_put_leg_symbol: lp,
                self.short_call_leg_symbol: sc,
                self.long_call_leg_symbol: lc,
            },
            index=underlying_prices.index,
        )

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return the 4-leg iron-condor weights DataFrame.

        Mode 1 (full iron condor):
            underlying = 0.0 (pure-options trade, no equity)
            short put  = -1 on writes, +1 on closes (Amount)
            long put   = +1 on writes, -1 on closes (Amount, BUYING)
            short call = -1 on writes, +1 on closes (Amount)
            long call  = +1 on writes, -1 on closes (Amount, BUYING)
            other      = 0
        Mode 2 (degenerate underlying-only):
            all weights = 0 (no trade — iron condor needs all 4 legs)
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
        # Iron condor is a pure-options trade — underlying weight 0.

        # Sign convention: short legs sell at write (-1), buy back at
        # close (+1). Long legs buy at write (+1), sell at close (-1).
        leg_signs = (
            (self.short_put_leg_symbol, -1.0),
            (self.long_put_leg_symbol, +1.0),
            (self.short_call_leg_symbol, -1.0),
            (self.long_call_leg_symbol, +1.0),
        )
        for leg_col, sign_at_write in leg_signs:
            if leg_col not in prices.columns:
                continue
            leg = prices[leg_col].to_numpy(dtype=float)
            write_mask, close_mask = _detect_lifecycle_events(leg)
            weights.loc[prices.index[write_mask], leg_col] = sign_at_write
            weights.loc[prices.index[close_mask], leg_col] = -sign_at_write
        return weights


def _detect_lifecycle_events(leg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Detect write/close events on any leg's price series.

    Same algorithm as ``covered_call_systematic._detect_lifecycle_events``
    — write event = zero-to-positive transition; close event =
    positive-to-zero transition. The 1e-3 epsilon distinguishes
    in-position bars (BS-priced premium) from flat bars (1e-6 floor
    set by the inner strategies).
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
