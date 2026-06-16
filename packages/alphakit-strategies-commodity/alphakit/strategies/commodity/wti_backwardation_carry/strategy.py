"""WTI long-only carry on the front-vs-next-month curve slope.

Implementation notes
====================

Foundational paper
------------------
Gorton, G. & Rouwenhorst, K. G. (2006).
*Facts and fantasies about commodity futures*.
Financial Analysts Journal, 62(2), 47–68.
https://doi.org/10.2469/faj.v62.n2.4083

GR06 documents that the long-run excess return on a fully-collateralised
commodity-futures portfolio is dominated by **roll yield** — the
return earned on a long position in a backwardated curve as the
contract rolls down toward spot. Curve slope, not spot price, is the
empirical engine of the commodity risk premium.

Primary methodology
-------------------
Erb, C. B. & Harvey, C. R. (2006).
*The strategic and tactical value of commodity futures*.
Financial Analysts Journal, 62(2), 69–97.
https://doi.org/10.2469/faj.v62.n2.4084

Section III ("The Term Structure Story") formalises the GR06 result
into a *tactical* allocation rule:

> "The futures curve provides a forward-looking risk-premium signal.
> Backwardated commodities (front > next) earn positive excess returns
> on a long position; contangoed commodities (front < next) earn
> negative excess returns on a long position."

EH06 demonstrates the rule on the 1982-2004 commodity panel and shows
that long-only positions in the most-backwardated commodities earn a
significant Sharpe over long-only positions in the most-contangoed
commodities. The strategy below applies the same rule to a single
commodity (WTI crude) using the front-vs-next-month curve slope as
the carry signal.

Why WTI specifically
--------------------
Crude oil exhibits the most pronounced and persistent backwardation
in the commodity panel (driven by storage and convenience-yield
dynamics: oil cannot be costlessly stored, and unscheduled demand
shocks bid up the front contract relative to the curve). Per EH06
Table III the WTI carry sub-strategy posts a Sharpe of ~0.6 over
the 1982-2004 sample — the highest single-commodity carry Sharpe
in the panel. We ship a WTI-specific strategy because the WTI carry
trade is the canonical demonstration of the EH06 §III rule.

Curve-slope signal
------------------
For each daily observation *t*::

    roll_yield(t) = (F1(t) - F2(t)) / F2(t)

where ``F1`` is the front-month contract price and ``F2`` is the
next-listed-month contract price. Positive roll yield = backwardation
(curve slopes downward); negative = contango (curve slopes upward).

The raw daily roll yield is noisy (intra-day mark-to-market jitter,
end-of-month roll mechanics, holiday-week distortions). We smooth
with a rolling mean over ``smoothing_days`` trading days (default
21 ≈ 1 month) before generating the signal, so the strategy does
not flip on single-day curve flickers.

Trading rule
------------
Long-only per EH06 §III:

* smoothed roll yield > ``backwardation_threshold`` → **+1** (long
  the front-month contract)
* otherwise → **0** (cash)

We deliberately do **not** short contango here. Shorting contango is
a different trade with different microstructure (storage costs,
short-borrow availability, contango-trap risk in deep-contango
regimes); ``ng_contango_short`` (Session 2E sibling) handles that
case explicitly for natural gas.

Sign convention
---------------
Output is a single-column DataFrame keyed on ``front_symbol`` —
the traded leg. ``next_symbol`` is read for the curve signal but
not traded. Values are in ``{0.0, +1.0}``. NaN is treated as zero
by the engine.

Edge cases
----------
* Before ``smoothing_days`` of history exist for both contracts, the
  strategy emits a zero signal.
* If either contract has a non-positive price, ``ValueError``.
* Missing column → ``KeyError`` with a clear message.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class WTIBackwardationCarry:
    """WTI crude-oil long-only carry on the front-vs-next-month curve slope.

    Long the front-month contract when the smoothed roll yield is
    positive (backwardation); flat otherwise. Single-asset strategy
    that *consumes* two columns (front and next) but *trades* only
    the front-month contract.

    Parameters
    ----------
    front_symbol
        Column name in the input DataFrame for the front-month WTI
        contract. Defaults to ``"CL=F"`` (yfinance continuous front).
    next_symbol
        Column name for the next-listed-month WTI contract. Defaults
        to ``"CL2=F"`` (yfinance second-contract continuous, used as
        the next-month proxy).
    smoothing_days
        Rolling-mean window for the roll-yield signal. Defaults to
        ``21`` (~ 1 month of trading days).
    backwardation_threshold
        Minimum smoothed roll yield to trigger a long position.
        Defaults to ``0.0`` — i.e. any positive smoothed roll yield is
        long. Set positive (e.g. ``0.001``) to require a clearly
        backwardated curve and reduce regime flips.
    """

    name: str = "wti_backwardation_carry"
    family: str = "commodity"
    asset_classes: tuple[str, ...] = ("commodity",)
    paper_doi: str = "10.2469/faj.v62.n2.4084"  # Erb/Harvey 2006 §III
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        front_symbol: str = "CL=F",
        next_symbol: str = "CL2=F",
        smoothing_days: int = 21,
        backwardation_threshold: float = 0.0,
    ) -> None:
        if not front_symbol:
            raise ValueError("front_symbol must be a non-empty string")
        if not next_symbol:
            raise ValueError("next_symbol must be a non-empty string")
        if front_symbol == next_symbol:
            raise ValueError(
                f"front_symbol and next_symbol must differ; got {front_symbol!r} for both"
            )
        if smoothing_days < 1:
            raise ValueError(f"smoothing_days must be >= 1, got {smoothing_days}")
        if backwardation_threshold < 0:
            raise ValueError(
                f"backwardation_threshold must be non-negative, got {backwardation_threshold}"
            )

        self.front_symbol = front_symbol
        self.next_symbol = next_symbol
        self.smoothing_days = smoothing_days
        self.backwardation_threshold = backwardation_threshold

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a ``{0.0, +1.0}`` signal DataFrame for the front contract.

        Parameters
        ----------
        prices
            DataFrame with at least the columns ``front_symbol`` and
            ``next_symbol``. Index is daily, values are continuous-
            contract closing prices.

        Returns
        -------
        signal
            Single-column DataFrame keyed on ``front_symbol``,
            aligned to ``prices.index``. Values in ``{0.0, +1.0}``.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=[self.front_symbol], dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        for col in (self.front_symbol, self.next_symbol):
            if col not in prices.columns:
                raise KeyError(
                    f"prices is missing required column {col!r}; got columns={list(prices.columns)}"
                )
        relevant = prices[[self.front_symbol, self.next_symbol]]
        if (relevant <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        front = prices[self.front_symbol]
        nxt = prices[self.next_symbol]

        roll_yield = (front - nxt) / nxt
        smoothed = roll_yield.rolling(self.smoothing_days).mean()

        signal = (smoothed > self.backwardation_threshold).astype(float)
        # Pre-warmup rows have NaN smoothed values → comparison is
        # False → already zero. ``fillna(0.0)`` handles any residual
        # NaN paths defensively.
        signal = signal.where(np.isfinite(smoothed), 0.0)

        return pd.DataFrame({self.front_symbol: signal}, index=prices.index)
