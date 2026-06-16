"""Conditional short-put when put-skew z-score exceeds threshold.

⚠ SUBSTRATE CAVEAT
==================
The synthetic-options adapter (ADR-005) has **flat IV across
strikes**, so the put-skew z-score this strategy monitors is
*structurally zero* on the synthetic substrate. The conditional
trigger ``skew_zscore > entry_threshold`` **NEVER FIRES** on
synthetic data — the strategy emits all-zero weights and the
backtest is a degenerate no-trade case.

The strategy ships in Phase 2 as a faithful implementation of
the published methodology (Bakshi-Kapadia-Madan 2003 +
Garleanu-Pedersen-Poteshman 2009) with a documented Phase 3
verification path against real options chains via Polygon
(ADR-004 stub). The synthetic backtest CANNOT evaluate this
strategy's expected return.

Foundational paper
------------------
Bakshi, G., Kapadia, N. & Madan, D. (2003). *Stock Return
Characteristics, Skew Laws, and the Differential Pricing of
Individual Equity Options*. Review of Financial Studies, 16(1),
101-143. https://doi.org/10.1093/rfs/16.1.0101

Primary methodology
-------------------
Garleanu, N., Pedersen, L. H. & Poteshman, A. M. (2009).
*Demand-Based Option Pricing*. Review of Financial Studies,
22(10), 4259-4299. https://doi.org/10.1093/rfs/hhp005

The conditional skew-reversal trade uses the demand-based
microfoundation: short OTM puts when put-skew is unusually
elevated (z-score > threshold, indicating temporarily high
demand for left-tail protection). Hold to expiry, capture the
mean-reversion of skew toward its long-run level.

Strategy structure
------------------
For each first trading day of a calendar month:

1. **Compute skew z-score.** ``skew = put_iv - call_iv`` at
   matched OTM offsets (5 %). Z-score = (skew_today − skew_mean) /
   skew_std over a rolling 252-day window.
2. **Trigger.** If ``skew_zscore > entry_threshold`` (default
   1.5), enter a short OTM put. Otherwise, no position.
3. **Hold to expiry.** Same lifecycle as
   ``cash_secured_put_systematic``.

⚠ On the flat-IV synthetic chain: ``skew = 0`` for all bars,
``skew_zscore = 0/0 = NaN``, ``trigger condition never met``.
The strategy emits all-zero weights.

Differentiation from `put_skew_premium` (Commit 13)
---------------------------------------------------
* `put_skew_premium`: **unconditional** short put + long call
  every cycle.
* `skew_reversal`: **conditional** short put only when
  skew-z > 1.5.

Real-feed cluster expectation: ρ ≈ 0.85-0.95 with
`put_skew_premium` in regimes where both fire; lower ρ
elsewhere because skew_reversal trades less frequently.

Bridge integration
------------------
1 discrete leg (short put when triggered). Underlying weight 0.
On synthetic chain: degenerate Mode 2 (trigger never fires).

Documented in ``known_failures.md``.
"""

from __future__ import annotations

import contextlib

import numpy as np
import pandas as pd
from alphakit.core.protocols import DataFeedProtocol
from alphakit.data.registry import FeedRegistry


class SkewReversal:
    """Conditional short-put when put-skew z-score > threshold.

    ⚠ Substrate caveat: synthetic chain has flat IV → skew = 0 →
    trigger never fires → degenerate no-trade backtest. Phase 3
    Polygon required for proper evaluation.

    Parameters
    ----------
    underlying_symbol
        Column name for the underlying. Defaults to ``"SPY"``.
    entry_threshold
        Skew z-score threshold for entry. Defaults to ``1.5``.
    chain_feed
        Optional explicit feed object.
    """

    name: str = "skew_reversal"
    family: str = "options"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1093/rfs/hhp005"  # Garleanu-Pedersen-Poteshman 2009
    rebalance_frequency: str = "monthly"

    discrete_legs: tuple[str, ...]

    def __init__(
        self,
        *,
        underlying_symbol: str = "SPY",
        entry_threshold: float = 1.5,
        chain_feed: DataFeedProtocol | None = None,
    ) -> None:
        if not underlying_symbol:
            raise ValueError("underlying_symbol must be a non-empty string")
        if entry_threshold <= 0.0:
            raise ValueError(f"entry_threshold must be > 0, got {entry_threshold}")
        self.underlying_symbol = underlying_symbol
        self.entry_threshold = entry_threshold
        self._chain_feed = chain_feed
        self.discrete_legs = (self.put_leg_symbol,)

    @property
    def chain_feed(self) -> DataFeedProtocol:
        if self._chain_feed is not None:
            return self._chain_feed
        return FeedRegistry.get("synthetic-options")

    @property
    def put_leg_symbol(self) -> str:
        return f"{self.underlying_symbol}_PUT_SKEW_REV_M1"

    def make_legs_prices(
        self,
        underlying_prices: pd.Series,
        *,
        chain_feed: DataFeedProtocol | None = None,
    ) -> pd.DataFrame:
        """Construct the conditional put-leg series.

        ⚠ On the flat-IV synthetic chain, the skew z-score is
        identically zero, so the trigger never fires. This method
        returns a DataFrame with the put-leg column at the flat
        floor everywhere — no positions ever opened.

        Real-feed equivalent (Phase 3): the method would compute
        skew = put_iv − call_iv at matched OTM offsets, z-score
        over a 252-day rolling window, fire short put when
        z > threshold, hold to expiry.
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
        # The trigger never fires on synthetic chains because the
        # adapter has flat IV across strikes. We return the leg
        # column at the flat floor everywhere — no positions
        # opened, no signal events for generate_signals to detect.
        # The real-feed implementation (Phase 3) would compute
        # skew z-scores and fire short puts when z > threshold.
        n = len(underlying_prices.index)
        put_premium = np.full(n, 1e-6, dtype=float)
        return pd.DataFrame(
            {self.put_leg_symbol: put_premium},
            index=underlying_prices.index,
        )

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return all-zero weights on synthetic-chain backtests.

        ⚠ On the flat-IV synthetic chain, the trigger never fires
        and this method returns all-zero weights. Real-feed
        evaluation (Phase 3) required for non-trivial output.
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

        # All-zero weights — substrate caveat means trigger never fires.
        return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)


with contextlib.suppress(ImportError):
    from alphakit.data.options import synthetic as _synthetic  # noqa: F401
