"""Swap-Treasury spread mean-reversion (Duarte/Longstaff/Yu 2007).

Implementation notes
====================

Foundational paper
------------------
Liu, J., Longstaff, F. A. & Mandell, R. E. (2006).
*The market price of risk in interest rate swaps: The roles of
default and liquidity risks*. Journal of Business, 79(5),
2337–2359.
https://doi.org/10.1086/505250

Documents the empirical dynamics of the swap spread (interest-rate-
swap rate minus matched-maturity Treasury yield) and decomposes it
into default-risk and liquidity-premium components. Establishes
that the spread is a stationary process with mean-reverting
dynamics around a slowly-moving long-run mean.

Primary methodology
-------------------
Duarte, J., Longstaff, F. A. & Yu, F. (2007).
*Risk and return in fixed-income arbitrage: nickels in front of
a steamroller?*. Review of Financial Studies, 20(3), 769–811.
https://doi.org/10.1093/rfs/hhl026

Documents and tests several fixed-income arbitrage strategies
including the swap-spread arbitrage. They find positive risk-
adjusted returns net of transaction costs but with material tail
risk during stress regimes (LTCM 1998, GFC 2008-09).

Why two papers
--------------
Liu/Longstaff/Mandell (2006) provides the *risk-factor* result:
swap spreads are mean-reverting around a long-run level driven by
default and liquidity. Duarte/Longstaff/Yu (2007) provides the
*expected-return* result: trading deviations from the long-run
mean has positive expected return after costs but large tail
risk. The synthesis: z-score the swap-spread proxy and trade
mean-reversion in both directions.

Differentiation from `curve_steepener_2s10s` and similar
---------------------------------------------------------
* The steepener / flattener / butterfly strategies trade the
  *yield-curve slope* on Treasuries alone.
* `swap_spread_mean_rev` (this strategy) trades the *swap-Treasury
  basis* — a different signal driven by funding costs, liquidity
  scarcity, and balance-sheet constraints rather than expected
  rate path.

The two signals are largely orthogonal in normal regimes (expected
ρ ≈ 0.1-0.2). They overlap during stress regimes when both the
slope and the swap spread move sharply (e.g. 2008 Q4: both flat-
inverted curve and elevated swap spread).

Algorithm
---------
For each daily bar:

1. Compute the log-price spread between the swap-rate proxy and
   the matched-maturity Treasury proxy::

       log_spread = log(P_treasury) − log(P_swap)

   When the swap rate is *higher* than the Treasury yield (positive
   swap spread, the typical regime), the swap-rate-derived bond
   price is *lower* than the Treasury bond price; ``log_spread``
   is *positive*. When the swap spread tightens or inverts (rare
   negative-swap-spread regime, e.g. 2010-15), ``log_spread``
   approaches zero or goes negative.

2. Z-score the log-price spread over a 252-day rolling window.

3. **Mean-reversion entry** (both directions):

   * ``z > +entry_threshold`` → swap rate is unusually rich vs
     Treasury → expect spread to tighten → SHORT Treasury, LONG
     swap (i.e. weight ``+1`` on swap leg, ``−1`` on Treasury leg).
   * ``z < −entry_threshold`` → swap rate is unusually cheap vs
     Treasury → expect spread to widen → LONG Treasury, SHORT
     swap.

4. **Exit** when ``|z| < exit_threshold``.

5. Equal dollar weights on each leg (DV01 mismatch is documented
   in `known_failures.md`).

Column convention
-----------------
2-column DataFrame in order ``[treasury_proxy, swap_proxy]``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class SwapSpreadMeanRev:
    """Mean-reversion on the swap-Treasury basis via log-price-spread z-score.

    Parameters
    ----------
    zscore_window
        Trailing window for the rolling z-score (default ``252``).
    entry_threshold
        Absolute z-score above which a position is entered
        (default ``1.0``).
    exit_threshold
        Absolute z-score below which an active position is exited
        (default ``0.25``).
    """

    name: str = "swap_spread_mean_rev"
    family: str = "rates"
    asset_classes: tuple[str, ...] = ("bond",)
    paper_doi: str = "10.1093/rfs/hhl026"  # Duarte/Longstaff/Yu 2007
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        zscore_window: int = 252,
        entry_threshold: float = 1.0,
        exit_threshold: float = 0.25,
    ) -> None:
        if zscore_window < 30:
            raise ValueError(f"zscore_window must be >= 30, got {zscore_window}")
        if entry_threshold <= 0:
            raise ValueError(f"entry_threshold must be positive, got {entry_threshold}")
        if exit_threshold < 0:
            raise ValueError(f"exit_threshold must be non-negative, got {exit_threshold}")
        if exit_threshold >= entry_threshold:
            raise ValueError(
                f"exit_threshold ({exit_threshold}) must be < entry_threshold "
                f"({entry_threshold}) for the entry/exit hysteresis to be well-defined"
            )

        self.zscore_window = zscore_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return mean-reversion weights on the Treasury / swap pair.

        Parameters
        ----------
        prices
            Two-column DataFrame in order ``[treasury_proxy,
            swap_proxy]``.

        Returns
        -------
        weights
            DataFrame aligned to ``prices``. When ``z > +entry``
            (swap rich) → swap weight = +1, Treasury weight = −1.
            When ``z < −entry`` (swap cheap) → swap weight = −1,
            Treasury weight = +1. Otherwise zero.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if prices.shape[1] != 2:
            raise ValueError(
                f"prices must have exactly 2 columns (treasury, swap), got {prices.shape[1]}"
            )
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        treasury_col, swap_col = prices.columns[0], prices.columns[1]
        log_spread = np.log(prices[treasury_col]) - np.log(prices[swap_col])

        rolling_mean = log_spread.rolling(self.zscore_window).mean()
        rolling_std = log_spread.rolling(self.zscore_window).std(ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            zscore = (log_spread - rolling_mean) / rolling_std
        zscore = zscore.replace([np.inf, -np.inf], np.nan)

        signal = np.zeros(len(prices), dtype=np.float64)
        active = 0  # +1 = "swap rich" position (long swap, short treasury); -1 = mirror
        z_arr = zscore.to_numpy()
        for i in range(len(z_arr)):
            if np.isnan(z_arr[i]):
                signal[i] = 0.0
                continue
            if active == 0:
                if z_arr[i] > self.entry_threshold:
                    active = +1
                elif z_arr[i] < -self.entry_threshold:
                    active = -1
            elif (active == +1 and z_arr[i] < self.exit_threshold) or (
                active == -1 and z_arr[i] > -self.exit_threshold
            ):
                active = 0
            signal[i] = float(active)

        treasury_weight = -signal
        swap_weight = signal

        return pd.DataFrame(
            {treasury_col: treasury_weight, swap_col: swap_weight},
            index=prices.index,
        )
