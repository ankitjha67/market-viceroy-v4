"""Frog-in-the-pan momentum (Da, Gurun, Warachka 2014).

Paper
-----
Da, Z., Gurun, U. G. & Warachka, M. (2014).
*Frog in the pan: continuous information and momentum*.
The Review of Financial Studies, 27(7), 2171–2218.
https://doi.org/10.1093/rfs/hhu003

The hypothesis
--------------
Behavioural finance argues investors under-react to *continuous*
information (many small updates, like a frog slowly boiling in a pan)
but over-react to *discrete* information (a single earnings surprise).
Consequently, momentum profits should be **larger for stocks with
continuous information** than for stocks whose past return is
dominated by a few big days.

The information-discreteness (ID) measure
-----------------------------------------
Over a formation window of ``F`` days:

    ID = sign(cumulative_return) * (pct_negative_days - pct_positive_days)

* ``pct_negative_days`` = fraction of days in the window with a
  negative simple return
* ``pct_positive_days`` = same for positive
* ``sign(cumulative_return)`` makes ID positive for "discrete" winners
  (few up days drove a positive cumulative return) and for "discrete"
  losers (few down days drove a negative cumulative return)

ID is in ``[-1, +1]``. Low ``|ID|`` means **continuous** information —
the stock trended smoothly — which is the sweet spot for momentum.

Signal construction (Phase 1 implementation)
---------------------------------------------
We build a continuity-weighted momentum signal:

    signal_i = cumulative_return_i * (1 - |ID_i|)

and rank cross-sectionally. Top decile is long, bottom decile short.
Equivalent to the paper's double-sort (first by momentum, then by ID)
on univariate ETF-style universes.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

_DAYS_PER_MONTH = 21


class FrogInThePan:
    """Continuity-weighted cross-sectional momentum (DGW 2014)."""

    name: str = "frog_in_the_pan"
    family: str = "trend"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1093/rfs/hhu003"
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        formation_months: int = 12,
        skip_months: int = 1,
        top_pct: float = 0.1,
        long_only: bool = False,
        min_positions_per_side: int = 1,
    ) -> None:
        if formation_months <= 0:
            raise ValueError(f"formation_months must be positive, got {formation_months}")
        if skip_months < 0:
            raise ValueError(f"skip_months must be non-negative, got {skip_months}")
        if skip_months >= formation_months:
            raise ValueError(
                f"skip_months ({skip_months}) must be < formation_months ({formation_months})"
            )
        if not 0.0 < top_pct <= 0.5:
            raise ValueError(f"top_pct must be in (0, 0.5], got {top_pct}")
        if min_positions_per_side < 1:
            raise ValueError(f"min_positions_per_side must be >= 1, got {min_positions_per_side}")
        self.formation_months = formation_months
        self.skip_months = skip_months
        self.top_pct = top_pct
        self.long_only = long_only
        self.min_positions_per_side = min_positions_per_side

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        # 1. Daily simple returns.
        daily_ret = prices.pct_change()

        # 2. Window sizes in trading days.
        effective_window_days = (self.formation_months - self.skip_months) * _DAYS_PER_MONTH
        skip_days = self.skip_months * _DAYS_PER_MONTH

        # 3. Cumulative return over the formation window via log-sum.
        log_ret = np.log1p(daily_ret)
        cum_log = log_ret.rolling(effective_window_days).sum()
        cum_ret = np.expm1(cum_log)

        # 4. Fraction of positive / negative days over the same window.
        pos_days = (daily_ret > 0).astype(float).rolling(effective_window_days).sum()
        neg_days = (daily_ret < 0).astype(float).rolling(effective_window_days).sum()
        pct_pos = pos_days / effective_window_days
        pct_neg = neg_days / effective_window_days

        # 5. Information discreteness.
        id_signal = np.sign(cum_ret) * (pct_neg - pct_pos)

        # 6. Continuity-weighted momentum.
        continuity = 1.0 - id_signal.abs()
        adjusted_signal = cum_ret * continuity

        # 7. Skip the most recent window.
        if skip_days > 0:
            adjusted_signal = adjusted_signal.shift(skip_days)

        # 8. Sample at month-ends and rank cross-sectionally.
        monthly_signal = adjusted_signal.resample("ME").last()

        n_symbols = len(prices.columns)
        n_top = max(self.min_positions_per_side, round(n_symbols * self.top_pct))
        if n_top * 2 > n_symbols and not self.long_only:
            n_top = max(1, n_symbols // 2)

        ranks = monthly_signal.rank(axis=1, ascending=False)
        valid = monthly_signal.notna()
        top_mask = (ranks <= n_top) & valid
        bot_mask = (ranks > n_symbols - n_top) & valid

        long_counts = top_mask.sum(axis=1).replace(0, np.nan)
        long_side = top_mask.astype(float).div(long_counts, axis=0)

        if self.long_only:
            monthly_weights = long_side
        else:
            short_counts = bot_mask.sum(axis=1).replace(0, np.nan)
            short_side = -bot_mask.astype(float).div(short_counts, axis=0)
            monthly_weights = long_side.add(short_side, fill_value=0.0)

        monthly_weights = monthly_weights.fillna(0.0)
        daily_weights = monthly_weights.reindex(prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights)
