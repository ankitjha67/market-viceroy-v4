"""Natural-gas short-only contango trade on the front-vs-next-month curve.

Implementation notes
====================

Foundational paper
------------------
Bessembinder, H. (1992).
*Systematic risk, hedging pressure, and risk premiums in futures markets*.
Review of Financial Studies, 5(4), 637–667.
https://doi.org/10.1093/rfs/5.4.637

Bessembinder (1992) decomposes the futures-curve risk premium into
hedging-pressure and macro-risk components and shows that
**contangoed commodities exhibit negative excess returns on long
positions** — equivalently, positive excess returns on short
positions. The contango short trade harvests the producer-hedging
premium that long-only investors *pay* for taking the storage side
of the trade.

Primary methodology
-------------------
Erb, C. B. & Harvey, C. R. (2006).
*The strategic and tactical value of commodity futures*.
Financial Analysts Journal, 62(2), 69–97.
https://doi.org/10.2469/faj.v62.n2.4084

Section III ("The Term Structure Story") implements both legs of
the curve premium — long backwardation, short contango — on the
1982-2004 commodity panel. The most-contangoed leg (natural gas)
posts the largest contango short-side premium in the panel.

Why NG specifically
-------------------
Natural gas exhibits the most pronounced and persistent contango in
the commodity panel for two structural reasons:

1. **Seasonal storage**: gas is *injected* into storage from April
   to October (cooling-demand season → low spot demand) and
   *withdrawn* from November to March (heating-demand season →
   high spot demand). The summer storage build pushes the front
   contract below the next contract by 5-15% — deep, stable
   contango from May through September almost every year.
2. **Storage cost drag**: NG is expensive to store
   (liquefaction + tank rental + boil-off + injection-withdrawal
   fees), so the no-arbitrage upper bound on the curve slope is
   large — contango can run wide before storage arbitrageurs are
   incentivised to flatten it.

The producer-hedging-pressure premium documented in Bessembinder
(1992) is therefore concentrated in NG: producers consistently
hedge-sell forward contracts to lock in revenue, paying the
short-side premium to speculators who take the other side. We ship
a NG-specific strategy because the NG contango short is the
canonical demonstration of the Bessembinder hedging-pressure
premium on a single asset.

Curve-slope signal
------------------
For each trading day *t*::

    roll_yield(t) = (F1(t) - F2(t)) / F2(t)

where ``F1`` is the front-month NG contract and ``F2`` is the
next-listed-month NG contract. **Negative** roll yield = contango
(curve slopes upward); positive = backwardation.

The raw daily series is noisy. We smooth with a rolling mean over
``smoothing_days`` trading days (default 21 ≈ 1 month) before
generating the signal.

Trading rule
------------
Short-only — the asymmetric mirror of ``wti_backwardation_carry``:

* smoothed roll yield < ``-contango_threshold`` → **−1** (short the
  front-month contract)
* otherwise → **0** (cash)

Sign convention
---------------
Output is a single-column DataFrame keyed on ``front_symbol`` —
the traded leg. ``next_symbol`` is read for the curve signal but
not traded. Values are in ``{−1.0, 0.0}``. NaN is treated as zero
by the engine.

Why short-only
--------------
The short-contango trade has different microstructure than the
long-backwardation trade in ``wti_backwardation_carry``:

* **Short-borrow availability**: futures shorts are mechanically
  trivial (no borrow / locate), but the strategy assumes
  `commission_bps` covers the typical bid-ask + clearing cost.
* **Contango-trap risk**: in deep-and-persistent contango regimes
  (e.g. NG summer 2009-2010), the short can earn the curve-slope
  return but *also* lose if spot prices rise faster than the
  curve flattens. The strategy is designed to harvest the curve
  premium, not bet on spot direction; users should overlay a
  spot-direction filter (e.g. monthly trend filter) for tighter
  risk control.

We deliberately do **not** *buy* backwardation here. The long-
backwardation NG trade is a different microstructure (winter
heating-demand season, weather-dependent) — kept separate from the
canonical contango short.

Edge cases
----------
* Before ``smoothing_days`` of history exist, the strategy emits
  a zero signal.
* Non-positive prices → ``ValueError``.
* Missing input columns → ``KeyError`` with a clear message.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class NGContangoShort:
    """Natural-gas short-only contango trade on the front-vs-next-month curve.

    Short the front-month NG contract when the smoothed roll yield is
    below ``-contango_threshold`` (deep contango); flat otherwise.
    Single-asset strategy that *consumes* two columns (front and next)
    but *trades* only the front-month contract.

    Parameters
    ----------
    front_symbol
        Column name for the front-month NG contract. Defaults to
        ``"NG=F"`` (yfinance continuous front).
    next_symbol
        Column name for the next-listed-month NG contract. Defaults
        to ``"NG2=F"`` (yfinance second-contract continuous).
    smoothing_days
        Rolling-mean window for the roll-yield signal. Defaults to
        ``21`` (~1 month of trading days).
    contango_threshold
        Minimum |smoothed roll yield| (positive number) below which
        the signal is zero. Defaults to ``0.0`` — i.e. any contango
        triggers a short. Set positive (e.g. ``0.02``) to require
        deep contango of >= 2% per month.
    """

    name: str = "ng_contango_short"
    family: str = "commodity"
    asset_classes: tuple[str, ...] = ("commodity",)
    paper_doi: str = "10.2469/faj.v62.n2.4084"  # Erb/Harvey 2006 §III
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        front_symbol: str = "NG=F",
        next_symbol: str = "NG2=F",
        smoothing_days: int = 21,
        contango_threshold: float = 0.0,
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
        if contango_threshold < 0:
            raise ValueError(f"contango_threshold must be non-negative, got {contango_threshold}")

        self.front_symbol = front_symbol
        self.next_symbol = next_symbol
        self.smoothing_days = smoothing_days
        self.contango_threshold = contango_threshold

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a ``{−1.0, 0.0}`` signal DataFrame for the front contract.

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
            aligned to ``prices.index``. Values in ``{-1.0, 0.0}``.
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

        # Short when smoothed roll yield is below -threshold (deep contango).
        short_mask = (smoothed < -self.contango_threshold) & np.isfinite(smoothed)
        signal = pd.Series(0.0, index=prices.index)
        signal[short_mask] = -1.0

        return pd.DataFrame({self.front_symbol: signal}, index=prices.index)
