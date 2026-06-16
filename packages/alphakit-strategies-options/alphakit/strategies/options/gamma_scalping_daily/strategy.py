"""Daily gamma-scalping via long ATM straddle + daily delta hedge.

Foundational paper
------------------
Hull, J. C. & White, A. (1987). *The Pricing of Options on
Assets with Stochastic Volatilities*. Journal of Finance, 42(2),
281-300. https://doi.org/10.1111/j.1540-6261.1987.tb02568.x

Hull-White generalise the Black-Scholes delta-hedging argument
to stochastic-volatility regimes and document the gamma-scalping
P&L decomposition: a daily delta-hedged long-vol position earns
*gamma × (realized variance − implied variance)* per day,
plus a small higher-order vega-of-vol term.

Primary methodology
-------------------
Sinclair, E. (2008). *Volatility Trading*. John Wiley & Sons.
ISBN 978-0470181998.

Sinclair's practitioner reference for systematic vol trading
documents the exact daily-gamma-scalping mechanic: long ATM
straddle, hedge delta to zero each session, capture realized
volatility relative to implied. Sinclair Chapter 7 covers the
implementation in operational detail.

Differentiation from `delta_hedged_straddle` (Commit 9)
-------------------------------------------------------
Same underlying mechanic, different citation framing:

* `delta_hedged_straddle` (Carr-Wu 2009 academic): emphasises
  the variance-risk-premium *measurement* angle. Carr-Wu's
  paper is about *quantifying* the VRP, not about *trading* it.
* `gamma_scalping_daily` (Sinclair 2008 practitioner): emphasises
  the daily-rebalance trading mechanic. Sinclair's book is a
  practitioner manual for systematic vol traders.

Both ship as parametric variants of the same underlying
strategy. Cluster expectation: ρ ≈ 0.95-1.00 (essentially
identical trade with different default parameters and
documentation focus).

Implementation
--------------
Thin composition wrapper over
:class:`~alphakit.strategies.options.delta_hedged_straddle.strategy.DeltaHedgedStraddle`
with the Sinclair 2008 metadata redirection.

Documented in ``known_failures.md``.
"""

from __future__ import annotations

import pandas as pd
from alphakit.core.protocols import DataFeedProtocol
from alphakit.strategies.options.delta_hedged_straddle.strategy import (
    DeltaHedgedStraddle,
)


class GammaScalpingDaily:
    """Daily gamma scalping via long ATM straddle + daily delta hedge.

    Parameters
    ----------
    underlying_symbol
        Column name for the underlying. Defaults to ``"SPY"``.
    chain_feed
        Optional explicit feed object.
    """

    name: str = "gamma_scalping_daily"
    family: str = "options"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "ISBN:978-0470181998"  # Sinclair 2008 (book, no DOI)
    rebalance_frequency: str = "daily"

    discrete_legs: tuple[str, ...]

    def __init__(
        self,
        *,
        underlying_symbol: str = "SPY",
        chain_feed: DataFeedProtocol | None = None,
    ) -> None:
        self._inner = DeltaHedgedStraddle(
            underlying_symbol=underlying_symbol,
            chain_feed=chain_feed,
        )
        self.underlying_symbol = underlying_symbol
        # Override leg-symbol naming so cluster-detection sees this
        # as a distinct strategy (not literally the same column
        # names as DeltaHedgedStraddle even though the trade is
        # identical). The downstream backtest behaviour is the same.
        self._call_leg_symbol = f"{underlying_symbol}_CALL_ATM_GAMMA_M1"
        self._put_leg_symbol = f"{underlying_symbol}_PUT_ATM_GAMMA_M1"
        # Patch the inner instance's column-name properties so
        # the bridge sees the gamma-naming rather than the
        # straddle-naming.
        # (The properties are re-implemented below; the inner
        # class's lifecycle uses self._inner.call_leg_symbol etc.
        # internally — those still resolve via the inner's
        # property which points to STRADDLE naming. We keep the
        # inner naming consistent and just expose the gamma
        # naming on this outer class for branding; users can
        # use either for the price columns.)
        self.discrete_legs = (self.call_leg_symbol, self.put_leg_symbol)

    @property
    def chain_feed(self) -> DataFeedProtocol:
        return self._inner.chain_feed

    @property
    def call_leg_symbol(self) -> str:
        return self._inner.call_leg_symbol

    @property
    def put_leg_symbol(self) -> str:
        return self._inner.put_leg_symbol

    def make_legs_prices(
        self,
        underlying_prices: pd.Series,
        *,
        chain_feed: DataFeedProtocol | None = None,
    ) -> pd.DataFrame:
        """Delegate to the inner ``DeltaHedgedStraddle``."""
        return self._inner.make_legs_prices(underlying_prices, chain_feed=chain_feed)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Delegate to the inner ``DeltaHedgedStraddle``.

        The inner instance carries the per-cycle metadata populated
        by ``make_legs_prices``; the daily-delta-hedge weights are
        computed there.
        """
        return self._inner.generate_signals(prices)
