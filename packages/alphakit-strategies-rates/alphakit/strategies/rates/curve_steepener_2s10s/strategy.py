"""2s10s curve steepener — mean-reversion on the slope of the US Treasury curve.

Implementation notes
====================

Foundational paper
------------------
Litterman, R. & Scheinkman, J. (1991).
*Common factors affecting bond returns*. Journal of Fixed Income, 1(1), 54–61.
Establishes the three-factor PCA decomposition of the yield curve
into level, slope and curvature. The 2s10s spread is the canonical
proxy for the second principal component (slope), and Litterman/
Scheinkman document its stationarity around a long-run mean.

Primary methodology
-------------------
Cochrane, J. H. & Piazzesi, M. (2005).
*Bond risk premia*. American Economic Review, 95(1), 138–160.
Establishes that a single linear combination of forward rates — the
"tent factor" — predicts excess returns on Treasury bonds across
maturities. The slope of the curve is one of the largest weights in
the tent factor, providing the academic anchor for slope-based
trading rules. When the slope deviates significantly from its
long-run mean, the implied excess-return forecast is asymmetric and
expected to mean-revert.
https://doi.org/10.1257/0002828053828581

Why two papers
--------------
Litterman/Scheinkman (1991) gives the *risk-factor* justification
for treating the slope as a stationary, mean-reverting variable.
Cochrane/Piazzesi (2005) gives the *expected-return* justification
for trading on its deviations from the mean. Neither paper
prescribes the explicit "narrow-spread → enter steepener" rule
implemented here; that rule is a market-practice synthesis of both
results, and ``paper.md`` is honest about that synthesis.

Steepener mechanics
-------------------
A 2s10s steepener position is **long the short-end / short the
long-end**. It profits when the yield spread (10Y yield − 2Y yield)
widens, which can happen via:

* The long-end yield rising more than the short-end (short the
  long-end leg gains), and/or
* The short-end yield falling more than the long-end (long the
  short-end leg gains).

The position is sized DV01-neutral so that parallel shifts in the
curve produce zero P&L: any pure-level move is hedged out, and the
remaining exposure is to the slope alone.

Published rules (slope mean-reversion synthesis)
------------------------------------------------
For each daily bar:

1. Compute the log-price spread between the long-end and short-end
   bond proxies::

       log_spread = log(long_end_price) − log(short_end_price)

   Because long-duration prices react more strongly to yield moves,
   a narrowing of the *yield spread* (10Y − 2Y falls) corresponds
   to a *rising* log-price spread (the long-end outperforms the
   short-end). The two are inversely related, so mean-reversion of
   the slope can be tested on either signal.

2. Z-score the log-price spread over a trailing window
   (default 252 trading days = 1 year)::

       z = (log_spread − rolling_mean) / rolling_std

3. Steepener entry: when ``z > +entry_threshold`` (the long-end
   has significantly outperformed → the yield spread is narrow vs
   history), set the steepener signal to 1.0. Mean-reversion
   implies the yield spread will widen, which earns positive P&L
   on a steepener position.

4. Exit: when the z-score falls back to ``< +exit_threshold``,
   close the position. The hysteresis avoids whipsaw flips around
   the entry boundary.

5. Position weights (DV01-neutral): when the steepener is active,
   set::

       short_end_weight = +signal / 2.0 × (long_duration / short_duration)
       long_end_weight  = −signal / 2.0

   The default duration ratio is 4.1 (10Y modified duration ≈ 8.0;
   2Y modified duration ≈ 1.95). Per unit of signal the long-leg
   gross is 0.5 of long-end notional and the short-leg gross is
   ~2.05 of short-end notional. Net dollar exposure is small and
   parallel-shift DV01 is zero by construction.

6. Hold daily — the signal is recomputed every bar. The strategy
   does **not** force monthly rebalancing because the entry/exit
   rule is event-driven on the z-score.

Column convention
-----------------
The strategy expects a 2-column ``prices`` DataFrame. The **first**
column is the short-end (e.g. SHY or a duration-2 bond proxy from
FRED ``DGS2``) and the **second** column is the long-end (e.g. TLT
or a duration-8 proxy from ``DGS10``). Passing 1 column or 3+
columns raises ``ValueError``.

DV01-neutral weights assume the configured durations are correct.
For real-feed Session 2H benchmarks, durations should be re-estimated
from the actual bond ETF or constructed from the FRED yield level
(modified duration of a constant-maturity synthetic ≈ maturity / (1+y)
for low yields).

Edge cases
----------
* Before ``zscore_window`` daily bars are available, the strategy
  emits zero weights.
* Constant prices (zero realised vol on the spread) emit zero
  weights — a zero standard deviation makes the z-score undefined.
* The signal is event-driven; weights can change at any bar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class CurveSteepener2s10s:
    """2s10s curve steepener via mean-reversion on the log-price spread.

    Parameters
    ----------
    zscore_window
        Trailing window (in trading days) for the rolling mean and
        standard deviation of the log-price spread. Defaults to
        ``252`` (≈ 1 year).
    entry_threshold
        Z-score above which the steepener is entered (z on
        log-price spread must be **above** ``+entry_threshold`` for
        entry — i.e. the long-end has outperformed and the yield
        spread is narrow vs history). Defaults to ``1.0``.
    exit_threshold
        Z-score below which the steepener is exited. The position
        is held while the z-score stays above ``+exit_threshold``
        and exited once it crosses back below. Defaults to ``0.25``.
    long_duration
        Modified duration of the long-end leg (default ``8.0`` for
        a 10Y constant-maturity Treasury).
    short_duration
        Modified duration of the short-end leg (default ``1.95``
        for a 2Y constant-maturity Treasury).
    """

    name: str = "curve_steepener_2s10s"
    family: str = "rates"
    asset_classes: tuple[str, ...] = ("bond",)
    paper_doi: str = "10.1257/0002828053828581"  # Cochrane/Piazzesi 2005
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        zscore_window: int = 252,
        entry_threshold: float = 1.0,
        exit_threshold: float = 0.25,
        long_duration: float = 8.0,
        short_duration: float = 1.95,
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
        if long_duration <= 0:
            raise ValueError(f"long_duration must be positive, got {long_duration}")
        if short_duration <= 0:
            raise ValueError(f"short_duration must be positive, got {short_duration}")
        if long_duration <= short_duration:
            raise ValueError(
                f"long_duration ({long_duration}) must be > short_duration "
                f"({short_duration}); a steepener requires the longer leg to be longer"
            )

        self.zscore_window = zscore_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.long_duration = long_duration
        self.short_duration = short_duration

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return DV01-neutral steepener weights aligned to ``prices``.

        Parameters
        ----------
        prices
            Two-column DataFrame indexed by daily timestamps. Column
            order: short-end, long-end. Values are total-return-
            adjusted closing prices (or duration-derived bond-price
            proxies in FRED-only environments).

        Returns
        -------
        weights
            DataFrame aligned to ``prices``. The short-end column
            carries a non-negative weight, the long-end column a
            non-positive weight, and both are zero whenever the
            steepener is not active.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if prices.shape[1] != 2:
            raise ValueError(
                f"prices must have exactly 2 columns (short-end, long-end), got {prices.shape[1]}"
            )
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        short_col, long_col = prices.columns[0], prices.columns[1]
        log_spread = np.log(prices[long_col]) - np.log(prices[short_col])

        rolling_mean = log_spread.rolling(self.zscore_window).mean()
        rolling_std = log_spread.rolling(self.zscore_window).std(ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            zscore = (log_spread - rolling_mean) / rolling_std
        zscore = zscore.replace([np.inf, -np.inf], np.nan)

        signal = np.zeros(len(prices), dtype=np.float64)
        active = False
        z_arr = zscore.to_numpy()
        for i in range(len(z_arr)):
            if np.isnan(z_arr[i]):
                signal[i] = 0.0
                continue
            if not active and z_arr[i] > self.entry_threshold:
                active = True
            elif active and z_arr[i] < self.exit_threshold:
                active = False
            signal[i] = 1.0 if active else 0.0

        duration_ratio = self.long_duration / self.short_duration
        short_weight = (signal / 2.0) * duration_ratio
        long_weight = -(signal / 2.0)

        return pd.DataFrame(
            {short_col: short_weight, long_col: long_weight},
            index=prices.index,
        )
