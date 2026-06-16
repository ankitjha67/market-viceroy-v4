"""Credit-spread momentum on investment-grade corporate bonds (Jostova et al. 2013).

Implementation notes
====================

Primary methodology
-------------------
Jostova, G., Nikolova, S., Philipov, A. & Stahel, C. W. (2013).
*Momentum in corporate bond returns*. Review of Financial Studies,
26(7), 1649–1693.
https://doi.org/10.1093/rfs/hht022

Documents that 6-month trailing returns on investment-grade and
high-yield corporate bonds predict the next 6 months' returns —
i.e. bond momentum is real, comparable in magnitude to equity
momentum, and most reliable on non-investment-grade segments.
The cleanest single-asset application is on a broad investment-
grade ETF (LQD) or on the IG credit spread itself.

Why a single primary citation
-----------------------------
Jostova et al. (2013) §III specifies the trailing-6-month-return
ranking and the cross-sectional / time-series momentum result
directly. No separate foundational paper is needed.

Differentiation from sibling momentum strategies
------------------------------------------------
* `bond_tsmom_12_1` — single-asset 12/1 momentum on Treasuries.
  Different asset class (sovereign vs corporate); expected ρ ≈
  0.3-0.5 in tandem-rates regimes, lower otherwise.
* `real_yield_momentum` — TIPS-derived momentum. Different asset
  class (real-rate-linked sovereign vs corporate); expected ρ ≈
  0.2-0.4.
* `duration_targeted_momentum` — cross-sectional duration-adjusted
  momentum on Treasuries. Different mechanic (cross-sectional vs
  time-series) and different universe.

Credit-spread momentum trades a *credit-cycle* signal that is
materially decoupled from rate momentum. In risk-on regimes
spreads tighten and IG credit out-performs Treasuries; in risk-off
regimes the reverse. The 6/0 momentum on credit captures the
persistence of the credit cycle.

Algorithm
---------
For each month-end ``t``:

1. Compute the trailing 6-month log return of the IG credit bond
   proxy. Jostova et al. use 6 months as the most reliable signal
   horizon for corporate bonds (longer than the 12/1 used for
   Treasuries because corporate-bond return autocorrelation is
   shorter).
2. Sign-of-return signal: +1 if positive, −1 if negative, 0 if
   ``|return| ≤ threshold``.
3. Hold one month, rebalance monthly.

The strategy is single-asset by default but trivially generalises
to a cross-section (multiple corporate-bond ETFs ranked by their
trailing 6-month returns, long top / short bottom).

Edge cases
----------
* Before ``lookback_months`` months are available, signals are zero.
* Constant prices emit zero signals.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class CreditSpreadMomentum:
    """Single-asset 6/0 momentum on investment-grade corporate bond returns.

    Parameters
    ----------
    lookback_months
        Trailing window in months (default ``6`` per Jostova et al.
        §III).
    skip_months
        Months to skip from the most recent end (default ``0``).
        Jostova et al. find no skip improves the corporate-bond
        signal, unlike the 12/1 convention used for Treasuries.
    threshold
        Absolute return below which the signal is zero (default
        ``0.0``).
    """

    name: str = "credit_spread_momentum"
    family: str = "rates"
    asset_classes: tuple[str, ...] = ("bond",)
    paper_doi: str = "10.1093/rfs/hht022"  # Jostova et al. 2013
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        lookback_months: int = 6,
        skip_months: int = 0,
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
        """Return {-1, 0, +1} momentum signals aligned to ``prices``."""
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
