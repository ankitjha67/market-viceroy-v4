"""2s5s10s curve butterfly — mean-reversion on the third PC of the curve.

Implementation notes
====================

Foundational and primary paper
------------------------------
Litterman, R. & Scheinkman, J. (1991).
*Common factors affecting bond returns*. Journal of Fixed Income, 1(1), 54–61.
DOI: 10.3905/jfi.1991.692347

Litterman/Scheinkman decompose the yield curve into three principal
components — level (PC1), slope (PC2) and curvature (PC3). The
2s5s10s butterfly isolates curvature exposure: a position long the
two wings (2Y and 10Y) and short the belly (5Y) profits when the
curvature factor moves *down* (the belly cheapens vs the linear
interpolation between the wings); the opposite position profits when
curvature moves *up*. The strategy implemented here trades the third
PC's mean-reversion via a price-space proxy.

Butterfly mechanics — what we are betting on
--------------------------------------------
The classic 2s5s10s butterfly is a **3-leg DV01-weighted trade**:

* **Long wings, short belly** (also called "buy the curve" or
  "concave butterfly"): long 2Y, short 5Y, long 10Y, sized so that
  each leg's DV01 contribution is balanced on parallel and slope
  shifts. Profits when the belly cheapens relative to the wings —
  i.e. the 5Y yield rises by more than the 2-10 average.
* **Short wings, long belly** (the mirror): short 2Y, long 5Y, short
  10Y. Profits when the belly richens relative to the wings — i.e.
  the 5Y yield falls by more than the 2-10 average.

Sized DV01-weighted, the butterfly is approximately neutral to PC1
(level) and PC2 (slope) shifts and exposes only the curvature factor.

Curvature signal
----------------
Direct PCA on a daily yield panel is noisy, so this implementation
uses a price-space proxy that is monotone in the curvature PC. For
3-column ``prices`` ``[short, belly, long]``::

    fly_price = log(P_belly) − ½ × (log(P_short) + log(P_long))

A *high* positive ``fly_price`` corresponds to the belly having
out-performed the linear average of the wings — i.e. the belly yield
fell by more than the 2-10 average — i.e. the belly is *rich* vs the
wings (5Y yield is unusually low relative to the linear interpolation
between 2Y and 10Y). Mean-reversion implies the belly yield will
revert upward, which earns positive P&L on a **short-belly** position
(short 5Y, long 2Y and 10Y).

A *low* negative ``fly_price`` is the mirror case: belly is cheap →
mean-reversion implies belly yield will revert downward → **long-belly**
position.

Published rules (mean-reversion synthesis)
------------------------------------------
For each daily bar:

1. ``fly_price = log(P_belly) − ½ × (log(P_short) + log(P_long))``.
2. ``z = (fly_price − rolling_mean) / rolling_std`` over a
   ``zscore_window``-day trailing window.
3. **Short-belly entry:** ``z > +entry_threshold``. The belly is rich
   vs the wings → mean-reversion expected to cheapen the belly →
   profit on a short-belly butterfly.
4. **Long-belly entry:** ``z < −entry_threshold``. The belly is cheap
   vs the wings → mean-reversion expected to richen the belly →
   profit on a long-belly butterfly.
5. **Exit:** ``|z| < exit_threshold``. The hysteresis avoids whipsaw
   flips when the z-score drifts near the entry boundary.
6. **DV01-weighted weights** when the butterfly is active. Per unit
   of signal magnitude, the wing weights and the belly weight are
   sized so that the DV01 contributions are balanced::

       wing_dv01_share = 0.5  (each wing contributes half the offsetting DV01)
       w_short = +signal × 0.5 × belly_duration / short_duration
       w_belly = −signal × 1.0
       w_long  = +signal × 0.5 × belly_duration / long_duration

   The convention here is that ``signal = +1`` corresponds to the
   short-belly butterfly (long wings / short belly) and ``signal = −1``
   to the long-belly butterfly. Default durations are 1.95 (2Y), 4.5
   (5Y), 8.0 (10Y).

Column convention
-----------------
The strategy expects a **3-column** ``prices`` DataFrame in order
``[short_end, belly, long_end]`` (e.g. ``[SHY, IEF, TLT]`` or
``[DGS2_proxy, DGS5_proxy, DGS10_proxy]``). Passing ≠ 3 columns
raises ``ValueError``.

DV01-weighted weights assume the configured durations are correct.
Real-feed Session 2H benchmarks should re-estimate durations from
each ETF's actual basket or from the FRED yield level.

Edge cases
----------
* Before ``zscore_window`` daily bars are available, the strategy
  emits zero weights.
* Constant ``fly_price`` (zero realised vol on the curvature signal)
  emits zero weights.
* The signal is event-driven; weights can change at any bar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class CurveButterfly2s5s10s:
    """2s5s10s curve butterfly via mean-reversion on a curvature proxy.

    Parameters
    ----------
    zscore_window
        Trailing window (in trading days) for the rolling mean and
        standard deviation. Defaults to ``252`` (≈ 1 year).
    entry_threshold
        Absolute z-score above which a butterfly position is entered.
        Defaults to ``1.0``.
    exit_threshold
        Absolute z-score below which any active butterfly is exited.
        Defaults to ``0.25``.
    short_duration
        Modified duration of the short-end wing (default ``1.95``).
    belly_duration
        Modified duration of the belly leg (default ``4.5``).
    long_duration
        Modified duration of the long-end wing (default ``8.0``).
    """

    name: str = "curve_butterfly_2s5s10s"
    family: str = "rates"
    asset_classes: tuple[str, ...] = ("bond",)
    paper_doi: str = "10.3905/jfi.1991.692347"  # Litterman/Scheinkman 1991
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        zscore_window: int = 252,
        entry_threshold: float = 1.0,
        exit_threshold: float = 0.25,
        short_duration: float = 1.95,
        belly_duration: float = 4.5,
        long_duration: float = 8.0,
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
        if short_duration <= 0:
            raise ValueError(f"short_duration must be positive, got {short_duration}")
        if belly_duration <= 0:
            raise ValueError(f"belly_duration must be positive, got {belly_duration}")
        if long_duration <= 0:
            raise ValueError(f"long_duration must be positive, got {long_duration}")
        if not (short_duration < belly_duration < long_duration):
            raise ValueError(
                f"durations must satisfy short_duration ({short_duration}) < "
                f"belly_duration ({belly_duration}) < long_duration ({long_duration}) "
                f"for the butterfly to be well-defined"
            )

        self.zscore_window = zscore_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.short_duration = short_duration
        self.belly_duration = belly_duration
        self.long_duration = long_duration

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return DV01-weighted butterfly weights aligned to ``prices``.

        Parameters
        ----------
        prices
            Three-column DataFrame indexed by daily timestamps. Column
            order: short-end, belly, long-end.

        Returns
        -------
        weights
            DataFrame aligned to ``prices``. When the position is
            "short-belly" (signal = +1), wings are positive and belly
            is negative; when "long-belly" (signal = −1), wings are
            negative and belly is positive; otherwise all zero.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if prices.shape[1] != 3:
            raise ValueError(
                f"prices must have exactly 3 columns (short, belly, long), got {prices.shape[1]}"
            )
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        short_col, belly_col, long_col = (
            prices.columns[0],
            prices.columns[1],
            prices.columns[2],
        )
        log_short = np.log(prices[short_col])
        log_belly = np.log(prices[belly_col])
        log_long = np.log(prices[long_col])
        fly_price = log_belly - 0.5 * (log_short + log_long)

        rolling_mean = fly_price.rolling(self.zscore_window).mean()
        rolling_std = fly_price.rolling(self.zscore_window).std(ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            zscore = (fly_price - rolling_mean) / rolling_std
        zscore = zscore.replace([np.inf, -np.inf], np.nan)

        signal = np.zeros(len(prices), dtype=np.float64)
        active = 0  # +1 = short-belly butterfly, -1 = long-belly butterfly, 0 = flat
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

        wing_share_short = 0.5 * self.belly_duration / self.short_duration
        wing_share_long = 0.5 * self.belly_duration / self.long_duration
        w_short = signal * wing_share_short
        w_belly = -signal
        w_long = signal * wing_share_long

        return pd.DataFrame(
            {short_col: w_short, belly_col: w_belly, long_col: w_long},
            index=prices.index,
        )
