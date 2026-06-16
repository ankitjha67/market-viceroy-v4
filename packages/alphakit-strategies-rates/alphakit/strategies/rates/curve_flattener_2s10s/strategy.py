"""2s10s curve flattener — mean-reversion on the slope of the US Treasury curve.

Mirror image of :class:`CurveSteepener2s10s`. Whereas the steepener
enters when the yield spread is *narrow* vs history (long-end has
outperformed → high log-price spread → high z), the flattener enters
when the yield spread is *wide* vs history (long-end has
under-performed → low log-price spread → low z).

Implementation notes
====================

Foundational paper
------------------
Litterman, R. & Scheinkman, J. (1991).
*Common factors affecting bond returns*. Journal of Fixed Income, 1(1), 54–61.
DOI: 10.3905/jfi.1991.692347

Primary methodology
-------------------
Cochrane, J. H. & Piazzesi, M. (2005).
*Bond risk premia*. American Economic Review, 95(1), 138–160.
https://doi.org/10.1257/0002828053828581

The economic justification mirrors the steepener exactly: the slope
is a stationary risk factor (Litterman/Scheinkman) and predictably
reverts to its mean (Cochrane/Piazzesi). When the curve is unusually
steep, a flattener earns positive expected return. When unusually
narrow, a steepener does. Running both as separate strategies is a
deliberate choice — they are mirror images by construction (expected
ρ ≈ −1.0) and should never be active at the same time.

Flattener mechanics
-------------------
A 2s10s flattener position is **long the long-end / short the
short-end**. It profits when the yield spread (10Y yield − 2Y yield)
*narrows*, which can happen via:

* The long-end yield falling more than the short-end (the long
  long-end leg gains as P_long rises), and/or
* The short-end yield rising more than the long-end (the short
  short-end leg gains as P_short falls).

DV01-neutral sizing means parallel curve shifts produce zero P&L;
the residual exposure is to the slope alone.

Published rules (slope mean-reversion synthesis)
------------------------------------------------
For each daily bar:

1. ``log_spread = log(long_end_price) − log(short_end_price)``.
2. ``z = (log_spread − rolling_mean) / rolling_std`` over a
   ``zscore_window``-day trailing window.
3. Flattener entry: ``z < −entry_threshold`` (the long-end has
   significantly under-performed → the yield spread is wide vs
   history). Mean-reversion implies the spread will narrow,
   earning positive P&L on a flattener.
4. Exit: ``z > −exit_threshold``. The hysteresis avoids whipsaw
   flips around the entry boundary.
5. DV01-neutral weights when the flattener is active::

       short_end_weight = −signal / 2 × (long_duration / short_duration)
       long_end_weight  = +signal / 2

Column convention is identical to the steepener: 2-column DataFrame
with short-end first, long-end second.

Edge cases match the steepener's behaviour: zero weights during
warm-up, zero weights when realised vol on the spread is zero, and
event-driven daily updates.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class CurveFlattener2s10s:
    """2s10s curve flattener via mean-reversion on the log-price spread.

    Parameters
    ----------
    zscore_window
        Trailing window (in trading days) for the rolling mean and
        standard deviation of the log-price spread. Defaults to
        ``252`` (≈ 1 year).
    entry_threshold
        Z-score absolute level above which the flattener is entered
        (z on log-price spread must be **below** ``-entry_threshold``
        for entry — i.e. the long-end has under-performed and the
        yield spread is wide vs history). Defaults to ``1.0``.
    exit_threshold
        Z-score absolute level below which the flattener is exited.
        The position is held while the z-score stays below
        ``-exit_threshold`` and exited once it crosses back above.
        Defaults to ``0.25``.
    long_duration
        Modified duration of the long-end leg (default ``8.0``).
    short_duration
        Modified duration of the short-end leg (default ``1.95``).
    """

    name: str = "curve_flattener_2s10s"
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
                f"({short_duration}); a flattener requires the longer leg to be longer"
            )

        self.zscore_window = zscore_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.long_duration = long_duration
        self.short_duration = short_duration

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return DV01-neutral flattener weights aligned to ``prices``.

        Parameters
        ----------
        prices
            Two-column DataFrame indexed by daily timestamps. Column
            order: short-end, long-end.

        Returns
        -------
        weights
            DataFrame aligned to ``prices``. The short-end column
            carries a non-positive weight, the long-end column a
            non-negative weight, and both are zero whenever the
            flattener is not active.
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
            if not active and z_arr[i] < -self.entry_threshold:
                active = True
            elif active and z_arr[i] > -self.exit_threshold:
                active = False
            signal[i] = 1.0 if active else 0.0

        duration_ratio = self.long_duration / self.short_duration
        short_weight = -(signal / 2.0) * duration_ratio
        long_weight = signal / 2.0

        return pd.DataFrame(
            {short_col: short_weight, long_col: long_weight},
            index=prices.index,
        )
