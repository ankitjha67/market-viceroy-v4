"""Breakeven inflation rotation — mean-reversion on TIPS vs nominal Treasury basis.

Implementation notes
====================

Foundational paper
------------------
Campbell, J. Y. & Shiller, R. J. (1996).
*A scorecard for indexed government debt*. NBER Macroeconomics Annual,
11, 155–197.
https://doi.org/10.2307/3585242

Establishes the analytical framework for inflation-indexed government
bonds and decomposes the term structure of breakeven inflation
into expected inflation and an inflation-risk premium. The two
components are mean-reverting around their long-run means, providing
the *risk-factor* justification for trading deviations.

Primary methodology
-------------------
Fleckenstein, M., Longstaff, F. A. & Lustig, H. (2014).
*The TIPS-Treasury bond puzzle*. Journal of Finance, 69(5), 2151–2197.
https://doi.org/10.1111/jofi.12032

Documents that TIPS and matched nominal Treasuries, after stripping
out inflation via inflation swaps, can trade at materially different
prices — sometimes by 200 bps or more during 2008-2009. The basis
converged eventually, providing an explicit *expected-return*
justification for trading the spread.

Why two papers
--------------
Campbell/Shiller (1996) gives the *risk-factor* result that
breakeven is a stationary, mean-reverting variable; Fleckenstein/
Longstaff/Lustig (2014) gives the *expected-return* result that
trading the TIPS-Treasury basis when it is at extreme levels has
positive expected return. Neither paper prescribes the explicit
"breakeven extreme → rotate" rule implemented here; that rule is a
market-practice synthesis of both results.

Rotation mechanics — what we are betting on
-------------------------------------------
A 10Y TIPS and a 10Y nominal Treasury have similar duration but
different inflation exposure:

* The nominal Treasury pays a fixed coupon → exposed to surprise
  inflation (loses real value when inflation rises).
* The TIPS pays a real coupon plus an inflation adjustment to
  principal → hedged against surprise inflation.

The breakeven inflation rate ``B = Y_nominal − Y_TIPS`` represents
the market's pricing of expected inflation plus an inflation-risk
premium. When ``B`` is **high** vs history, the market is pricing
*high* inflation expectations; mean-reversion implies inflation
realised will under-perform expectations, and TIPS will under-
perform nominals (real coupons stay flat while nominals re-price
higher real yields). The rotation is therefore: SHORT TIPS / LONG
nominal.

When ``B`` is **low** vs history (e.g. 2009 deflation scare, 2020
March panic), mean-reversion implies inflation realised will out-
perform expectations, and TIPS out-perform nominals. Rotation:
LONG TIPS / SHORT nominal.

Breakeven proxy from prices
---------------------------
Direct breakeven yield computation requires the FRED `T10YIE` series.
The price-space proxy used here exploits the duration-symmetry of
matched-maturity TIPS and nominal Treasuries: when the breakeven
yield rises, the nominal price falls more than the TIPS price (the
nominal is the one re-pricing higher real yields), so::

    log_spread = log(P_TIPS) − log(P_nominal)

increases when breakeven rises, and decreases when it falls. The
strategy z-scores this proxy and trades the rotation in both
directions, exactly mirroring the steepener/flattener mechanic on
the slope.

Published rules
---------------
For each daily bar:

1. ``log_spread = log(P_TIPS) − log(P_nominal)``.
2. ``z = (log_spread − rolling_mean) / rolling_std`` over a
   ``zscore_window``-day trailing window.
3. **Short-TIPS rotation:** ``z > +entry_threshold`` (breakeven
   elevated, TIPS pricing in unsustainable inflation expectations).
   Short TIPS, long nominal.
4. **Long-TIPS rotation:** ``z < −entry_threshold`` (breakeven
   depressed, TIPS pricing in unsustainable disinflation).
   Long TIPS, short nominal.
5. **Exit:** ``|z| < exit_threshold``.

Position sizing assumes equal duration of TIPS and nominal: weights
are ±1.0 / ∓1.0 (signal × 1.0 on TIPS leg, opposite-sign signal × 1.0
on nominal leg). The duration mismatch in real ETFs (TIP duration ≈
7.5 vs IEF duration ≈ 8.0) is small; documented as a known failure
mode rather than a fix.

Column convention
-----------------
The strategy expects a 2-column ``prices`` DataFrame in order
``[tips_proxy, nominal_proxy]`` (e.g. ``[TIP, IEF]`` or
``[DFII10_proxy, DGS10_proxy]``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class BreakevenInflationRotation:
    """TIPS vs nominal Treasury rotation on breakeven inflation z-score.

    Parameters
    ----------
    zscore_window
        Trailing window for the breakeven proxy z-score (default ``252``).
    entry_threshold
        Absolute z-score above which a rotation is entered (default
        ``1.0``).
    exit_threshold
        Absolute z-score below which any active rotation is exited
        (default ``0.25``).
    """

    name: str = "breakeven_inflation_rotation"
    family: str = "rates"
    asset_classes: tuple[str, ...] = ("bond",)
    paper_doi: str = "10.1111/jofi.12032"  # Fleckenstein/Longstaff/Lustig 2014
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
        """Return rotation weights aligned to ``prices``.

        Parameters
        ----------
        prices
            Two-column DataFrame indexed by daily timestamps. Column
            order: TIPS proxy, nominal Treasury proxy.

        Returns
        -------
        weights
            DataFrame aligned to ``prices``. When in a "long-TIPS"
            rotation (signal = +1): ``+1`` on TIPS, ``-1`` on nominal.
            When in a "short-TIPS" rotation (signal = -1): ``-1`` on
            TIPS, ``+1`` on nominal. Otherwise both zero.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if prices.shape[1] != 2:
            raise ValueError(
                f"prices must have exactly 2 columns (tips, nominal), got {prices.shape[1]}"
            )
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        tips_col, nominal_col = prices.columns[0], prices.columns[1]
        log_spread = np.log(prices[tips_col]) - np.log(prices[nominal_col])

        rolling_mean = log_spread.rolling(self.zscore_window).mean()
        rolling_std = log_spread.rolling(self.zscore_window).std(ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            zscore = (log_spread - rolling_mean) / rolling_std
        zscore = zscore.replace([np.inf, -np.inf], np.nan)

        signal = np.zeros(len(prices), dtype=np.float64)
        active = 0  # +1 = long-TIPS rotation, -1 = short-TIPS rotation
        z_arr = zscore.to_numpy()
        for i in range(len(z_arr)):
            if np.isnan(z_arr[i]):
                signal[i] = 0.0
                continue
            if active == 0:
                if z_arr[i] < -self.entry_threshold:
                    active = +1
                elif z_arr[i] > self.entry_threshold:
                    active = -1
            elif (active == +1 and z_arr[i] > -self.exit_threshold) or (
                active == -1 and z_arr[i] < self.exit_threshold
            ):
                active = 0
            signal[i] = float(active)

        tips_weight = signal
        nominal_weight = -signal

        return pd.DataFrame(
            {tips_col: tips_weight, nominal_col: nominal_weight},
            index=prices.index,
        )
