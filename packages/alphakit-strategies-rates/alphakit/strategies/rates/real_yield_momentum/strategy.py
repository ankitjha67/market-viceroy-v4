"""Time-series momentum on TIPS real-yield-derived bond returns, 12/1.

Implementation notes
====================

Foundational paper
------------------
Pflueger, C. E. & Viceira, L. M. (2011).
*An empirical decomposition of risk and liquidity premia in
government bonds*. NBER Working Paper 16892.
https://doi.org/10.3386/w16892

Decomposes TIPS yields into a real-rate component and a liquidity
premium, and documents that real yields exhibit persistent
mean-reverting dynamics around macro state variables. Provides the
*risk-factor* justification for treating TIPS-derived returns as a
distinct asset class from nominal Treasuries.

Primary methodology
-------------------
Asness, C. S., Moskowitz, T. J. & Pedersen, L. H. (2013).
*Value and momentum everywhere*. Journal of Finance, 68(3), 929–985.
Section V applies the 12/1 time-series-momentum rule across asset
classes including bonds. The same momentum rule generalises to TIPS
real-yield-derived returns, providing the *expected-return*
justification.
https://doi.org/10.1111/jofi.12021

Why two papers
--------------
Pflueger/Viceira (2011) does not prescribe a momentum trading rule;
it documents the mean-reverting dynamics of real yields and
decomposes the components of TIPS pricing. Asness/Moskowitz/Pedersen
(2013) §V documents that 12/1 momentum works across asset classes
including bonds. The synthesis is the canonical Asness §V rule
applied to a TIPS-real-yield-derived bond return series rather than
nominal-yield-derived returns.

Differentiation from `bond_tsmom_12_1`
--------------------------------------
* `bond_tsmom_12_1` — 12/1 momentum on a *nominal* bond return series
  (TLT or DGS10-derived).
* `real_yield_momentum` (this strategy) — 12/1 momentum on a *real*
  bond return series (TIP or DFII10-derived).

The two strategies trade highly-correlated signals during regime-
stable periods (when nominal and real yields move together via the
parallel-shift PC1) and divergent signals during inflation-regime
shocks (when the breakeven component decouples them). Documented in
known_failures.md as ρ ≈ 0.6-0.8.

Asset-construction note
-----------------------
The strategy operates on a bond-price-like DataFrame. When the only
feed available is FRED's `DFII10` (constant-maturity 10Y TIPS yield),
callers convert real yield changes to bond-return-equivalent prices
via the same duration approximation documented for `bond_tsmom_12_1`::

    real_bond_return ≈ -duration * Δ(real_yield)

For the 10Y TIPS the modified duration is approximately 7.5 years
(slightly lower than the 8.0-year duration of the matched nominal
because TIPS amortise principal partly through inflation accrual).
The approximation drops convexity and the inflation-accrual term;
the *sign* of any 11-month cumulative real-bond-return is preserved
because both terms bias the *level* of returns rather than the sign.

Published rules
---------------
Identical to `bond_tsmom_12_1` mechanic on a real-yield-derived
price series:

1. Resample to month-end and compute monthly log returns.
2. Trailing return over months ``[t−12, t−1)`` (11-month effective
   window with the standard 1-month skip).
3. Sign-of-return signal: +1 if positive, −1 if negative, 0 if
   |return| ≤ threshold.
4. Hold one month, rebalance monthly.

Edge cases match `bond_tsmom_12_1`: zero signals during warm-up,
zero on constant prices, monthly piecewise constancy.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class RealYieldMomentum:
    """12/1 time-series momentum on TIPS real-yield-derived bond returns.

    Parameters
    ----------
    lookback_months
        Total months of history sampled (default ``12``).
    skip_months
        Months to skip from the most recent end (default ``1``).
    threshold
        Absolute return below which the signal is zero (default ``0.0``).
    """

    name: str = "real_yield_momentum"
    family: str = "rates"
    asset_classes: tuple[str, ...] = ("bond",)
    paper_doi: str = "10.1111/jofi.12021"  # Asness/Moskowitz/Pedersen 2013 §V
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
        """Return a {-1, 0, +1} signal DataFrame aligned to ``prices``.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps, columns are TIPS
            bond proxy symbols (e.g. ``[TIP]`` or
            ``[DFII10_proxy]``), values are real-yield-derived
            price-equivalents.
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
