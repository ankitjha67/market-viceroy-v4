"""Short ATM straddle as variance-swap approximation (Carr-Wu §2).

Foundational paper
------------------
Bondarenko, O. (2014). *Why Are Put Options So Expensive?*.
Quarterly Journal of Finance, 4(1), 1450015.
https://doi.org/10.1142/S2010139214500050

Bondarenko documents the variance risk premium empirically and
provides the empirical foundation for harvesting strategies.

Primary methodology
-------------------
Carr, P. & Wu, L. (2009). *Variance Risk Premia*. Review of
Financial Studies, 22(3), 1311-1341.
https://doi.org/10.1093/rfs/hhn038

Carr-Wu §2 derives the model-free **variance-swap-replication
formula**: a weighted portfolio of OTM puts and calls (with
weights ∝ 2/K²) replicates the variance swap rate. This is the
canonical setup for harvesting the variance risk premium without
model risk.

Implementation: a 2-leg approximation
-------------------------------------
The full Carr-Wu §2 replication uses an **integral over the strike
grid** with weights 2/K². The synthetic chain provides 9 strikes
spanning 0.80×–1.20× spot — a coarse grid that doesn't support
the integral cleanly. This strategy ships a **simpler 2-leg
approximation**: short ATM call + short ATM put (= short ATM
straddle), which captures the at-the-money portion of the
variance-swap-replicating portfolio.

Honestly documented as an *approximation* in the variance-swap
formula's spirit, not a literal replication. The full multi-strike
replication is deferred to Phase 3 with Polygon (denser strike
grid + dynamic weight computation).

Differentiation from siblings
-----------------------------
* vs ``delta_hedged_straddle`` (Commit 9): ρ ≈ -0.7 to -0.9
  (this strategy is the **short** side of the same straddle —
  opposite VRP direction; expected POSITIVE return per Carr-Wu's
  short-vol-earns-VRP result).
* vs ``gamma_scalping_daily`` (Commit 10): ρ ≈ -0.7 to -0.9
  (same opposite-side relationship).
* vs ``short_strangle_monthly`` (Commit 7): ρ ≈ 0.85-0.95
  (same direction with ATM strikes vs 10 % OTM strikes;
  variance_risk_premium_synthetic captures more premium per
  cycle but bears more tail risk).
* vs ``covered_call_systematic`` (Commit 2): ρ ≈ 0.55-0.75
  (covered call is single-leg + equity beta; this is 2-leg
  pure-options).

Bridge integration: 2 short-leg discrete dispatch
-------------------------------------------------
Composition wrapper combining
``CoveredCallSystematic(otm_pct=0.0)`` and
``CashSecuredPutSystematic(otm_pct=0.0)``. Both inner strategies
write at ATM strikes (synthetic chain's 1.00× spot grid point).
The outer strategy combines their leg outputs and emits SHORT
weights (-1 at write, +1 at close) on both option columns. No
underlying weight (pure-options trade).

The strategy declares ``discrete_legs = (call_leg, put_leg)``;
the bridge dispatches ``Amount`` semantics to both.

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


class VarianceRiskPremiumSynthetic:
    """Short ATM straddle (Carr-Wu §2 variance-swap approximation).

    Parameters
    ----------
    underlying_symbol
        Column name for the underlying. Defaults to ``"SPY"``.
        Pure-options trade — no underlying weight emitted.
    chain_feed
        Optional explicit feed object.
    """

    name: str = "variance_risk_premium_synthetic"
    family: str = "options"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1093/rfs/hhn038"  # Carr-Wu 2009 (primary)
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
        # ATM call write (otm_pct=0.0 — relaxed validation in
        # CoveredCallSystematic and CashSecuredPutSystematic permits this).
        self._short_call = CoveredCallSystematic(
            underlying_symbol=underlying_symbol,
            otm_pct=0.0,
            chain_feed=chain_feed,
        )
        self._short_put = CashSecuredPutSystematic(
            underlying_symbol=underlying_symbol,
            otm_pct=0.0,
            chain_feed=chain_feed,
        )
        self.discrete_legs = (self.call_leg_symbol, self.put_leg_symbol)

    @property
    def chain_feed(self) -> DataFeedProtocol:
        return self._short_call.chain_feed

    @property
    def call_leg_symbol(self) -> str:
        return self._short_call.call_leg_symbol

    @property
    def put_leg_symbol(self) -> str:
        return self._short_put.put_leg_symbol

    def make_legs_prices(
        self,
        underlying_prices: pd.Series,
        *,
        chain_feed: DataFeedProtocol | None = None,
    ) -> pd.DataFrame:
        """Construct both ATM-leg premium series.

        Returns a DataFrame indexed like ``underlying_prices`` with
        2 columns: ATM call leg + ATM put leg.
        """
        sc = self._short_call.make_call_leg_prices(underlying_prices, chain_feed=chain_feed)
        sp = self._short_put.make_put_leg_prices(underlying_prices, chain_feed=chain_feed)
        return pd.DataFrame(
            {self.call_leg_symbol: sc, self.put_leg_symbol: sp},
            index=underlying_prices.index,
        )

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return short-ATM-straddle weights.

        Mode 1 (full short ATM straddle):
            underlying = 0.0 (pure-options trade)
            call leg   = -1 on writes, +1 on closes (Amount, short)
            put leg    = -1 on writes, +1 on closes (Amount, short)
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
        for leg_col in (self.call_leg_symbol, self.put_leg_symbol):
            if leg_col not in prices.columns:
                continue
            leg = prices[leg_col].to_numpy(dtype=float)
            write_mask, close_mask = _detect_lifecycle_events(leg)
            weights.loc[prices.index[write_mask], leg_col] = -1.0  # SHORT at write
            weights.loc[prices.index[close_mask], leg_col] = 1.0  # buy back at close
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
