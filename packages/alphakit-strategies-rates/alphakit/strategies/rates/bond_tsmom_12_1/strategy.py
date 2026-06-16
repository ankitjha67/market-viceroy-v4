"""Time-series momentum on 10-year treasury returns, 12/1.

Implementation notes
====================

Foundational paper
------------------
Moskowitz, T. J., Ooi, Y. H. & Pedersen, L. H. (2012).
*Time series momentum*. Journal of Financial Economics, 104(2), 228–250.
https://doi.org/10.1016/j.jfineco.2011.11.003

Primary methodology
-------------------
Asness, C. S., Moskowitz, T. J. & Pedersen, L. H. (2013).
*Value and momentum everywhere*. Journal of Finance, 68(3), 929–985.
Section V applies the 12/1 time-series-momentum rule to 10-year
sovereign bond futures across G10 markets and validates the strategy
on fixed income.
https://doi.org/10.1111/jofi.12021

Published rules (Asness §V applied to a single bond)
----------------------------------------------------
For each month-end *t*:

1. Compute the trailing return over the 12 months ending one month
   prior, i.e. the return over months ``[t-12, t-1)``. Skipping the
   most recent month is the standard "12-1" convention from
   Moskowitz/Ooi/Pedersen (2012).

2. The **sign** of that lookback return determines the signal:

   * ``> +threshold`` → +1 (long the bond)
   * ``< -threshold`` → −1 (short the bond)
   * ``|return| ≤ threshold`` → 0 (flat)

3. Hold the signal for one month, rebalance at the next month-end.

The signal is intentionally discrete — Asness §V sizes positions to a
constant volatility target across the global bond panel; on a single
bond there is no cross-sectional sizing to perform, so we expose the
raw {−1, 0, +1} signal and leave volatility-targeting to a portfolio
overlay.

Bond-return approximation
-------------------------
The strategy operates on a price-like DataFrame. When the only feed
available is FRED's constant-maturity yield series (``DGS10``) and not
a bond-index price level, callers should pre-convert yield changes
to approximate bond returns via the standard duration approximation::

    bond_return ≈ -duration * delta_yield

For the 10Y constant-maturity series the modified duration is
approximately 8 years (varies with the yield level; ≈ 8.0 at 4% yield,
≈ 9.0 at 2% yield). The approximation drops the convexity term and
the carry component (yield × dt). Both are small over a single month
relative to duration × Δy, but they bias the **level** of returns,
not the **sign** — the 12/1 momentum signal is derived from the sign
of the cumulative monthly return, so it is robust to the bias.

When TLT (or another tradeable bond ETF) is available, prefer its
total-return adjusted-close price directly; the duration approximation
is a fallback for FRED-only environments.

Sign convention
---------------
We return **weights** (one column per input symbol) on the discrete
{−1, 0, +1} grid. The bridges interpret these as long / flat / short
target weights with a notional book of 1×. ``NaN`` is treated as
zero by the engine.

Edge cases
----------
* Before ``lookback_months`` months of history are available, the
  strategy emits zero signals.
* Constant prices over the lookback window emit zero signals
  (no momentum, no direction).
* Output is forward-filled at month-ends to align to the input daily
  index — within-month bars carry the most recent month-end signal.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class BondTSMOM12m1m:
    """Single-asset 12/1 time-series momentum on bond returns.

    Parameters
    ----------
    lookback_months
        Total months of history sampled (inclusive of the skip window).
        Defaults to ``12`` per Moskowitz/Ooi/Pedersen (2012) and
        Asness/Moskowitz/Pedersen (2013) §V.
    skip_months
        Most-recent months to *skip* when forming the lookback return.
        Defaults to ``1``.
    threshold
        Absolute return below which the signal is zero (flat). Defaults
        to ``0.0`` — i.e. emit a signal on every non-zero lookback
        return. Set positive (e.g. 0.005) to reduce signal flips in
        flat regimes.
    """

    name: str = "bond_tsmom_12_1"
    family: str = "rates"
    asset_classes: tuple[str, ...] = ("bond",)
    paper_doi: str = "10.1111/jofi.12021"  # Asness/Moskowitz/Pedersen 2013
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        lookback_months: int = 12,
        skip_months: int = 1,
        threshold: float = 0.0,
    ) -> None:
        if lookback_months <= 0:
            raise ValueError(f"lookback_months must be positive, got {lookback_months}")
        if skip_months < 0:
            raise ValueError(f"skip_months must be non-negative, got {skip_months}")
        if skip_months >= lookback_months:
            raise ValueError(
                f"skip_months ({skip_months}) must be < lookback_months ({lookback_months})"
            )
        if threshold < 0:
            raise ValueError(f"threshold must be non-negative, got {threshold}")

        self.lookback_months = lookback_months
        self.skip_months = skip_months
        self.threshold = threshold

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a {−1, 0, +1} signal DataFrame aligned to ``prices``.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps, columns are bond
            symbols, values are total-return-adjusted closing prices.
            For single-asset use, supply a one-column frame.

        Returns
        -------
        signal
            DataFrame aligned to ``prices``. Each value is in
            ``{-1.0, 0.0, +1.0}``. Pre-warmup rows are zero.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        month_end_prices = prices.resample("ME").last()
        monthly_log_returns = np.log(month_end_prices / month_end_prices.shift(1))

        effective_window = self.lookback_months - self.skip_months
        lookback_returns = (
            monthly_log_returns.rolling(effective_window).sum().shift(self.skip_months)
        )

        signal = pd.DataFrame(0.0, index=lookback_returns.index, columns=lookback_returns.columns)
        signal = signal.where(lookback_returns.abs() <= self.threshold, np.sign(lookback_returns))

        daily_signal = signal.reindex(prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_signal)
