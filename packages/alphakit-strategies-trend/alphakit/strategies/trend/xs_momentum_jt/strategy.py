"""Cross-sectional momentum, Jegadeesh & Titman (1993).

Paper
-----
Jegadeesh, N. & Titman, S. (1993).
*Returns to buying winners and selling losers: implications for stock
market efficiency*. The Journal of Finance, 48(1), 65–91.
https://doi.org/10.1111/j.1540-6261.1993.tb04702.x

Rules
-----
At every month-end:

1. Compute each stock's trailing ``formation_months`` return.
2. Rank stocks cross-sectionally on this return.
3. Buy the top ``top_pct`` (equal-weighted within the long side).
4. Short the bottom ``top_pct`` (equal-weighted within the short side).
5. Hold for one month, rebalance monthly.

The original paper tests multiple (J, K) formation/holding combinations
from 3 to 12 months; the best-performing combination is 6/6 on a
monthly rebalance, which is our default.

Notes vs. the paper
-------------------
* We skip the most recent month (``skip_months=1``) to avoid
  short-term reversal contamination, same convention as
  ``tsmom_12_1``. JT (1993) do not skip, but every follow-up paper
  since Jegadeesh (1990) does, and the effect is significantly
  cleaner with skipping.
* "Top decile" is defined by ``top_pct`` and rounded to at least 1
  position per side, so the strategy remains well-defined on small
  ETF universes (e.g. 6 instruments) as well as the paper's NYSE/AMEX
  panel.
* Long-only mode (``long_only=True``) drops the short side for
  jurisdictions where shorting is restricted or expensive.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class CrossSectionalMomentumJT:
    """Cross-sectional momentum (Jegadeesh-Titman 1993).

    Parameters
    ----------
    formation_months
        Trailing window over which to rank stocks. Defaults to ``6``.
    skip_months
        Most-recent months to skip before ranking. Defaults to ``1``
        (follows Jegadeesh 1990 reversal evidence).
    top_pct
        Fraction of the universe to hold on the long side (and short
        side, symmetrically). Defaults to ``0.1`` (top/bottom decile).
    long_only
        If ``True``, drop the short side. Defaults to ``False``.
    min_positions_per_side
        Lower bound on the number of instruments held on each side.
        Keeps the strategy well-defined on tiny universes. Defaults
        to ``1``.
    """

    name: str = "xs_momentum_jt"
    family: str = "trend"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1111/j.1540-6261.1993.tb04702.x"
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        formation_months: int = 6,
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

        # 1. Resample to month-ends.
        month_end_prices = prices.resample("ME").last()

        # 2. Formation return: product of monthly returns over
        #    [t - formation, t - skip). We use pct_change over the
        #    effective window and shift to honour the skip.
        effective_window = self.formation_months - self.skip_months
        formation_return = month_end_prices.pct_change(effective_window).shift(self.skip_months)

        # 3. Rank each row (ascending=False so rank 1 = best).
        n_symbols = len(prices.columns)
        n_top = max(self.min_positions_per_side, round(n_symbols * self.top_pct))
        if n_top * 2 > n_symbols and not self.long_only:
            # Universe too small for long/short: collapse to long-only.
            n_top = max(1, n_symbols // 2)

        ranks = formation_return.rank(axis=1, ascending=False)

        # 4. Top and bottom masks, gated on having a finite formation
        #    return to avoid picking up leading-NaN rows.
        valid = formation_return.notna()
        top_mask = (ranks <= n_top) & valid
        bottom_mask = (ranks > n_symbols - n_top) & valid

        # 5. Equal-weight within each side. Avoid division by zero on
        #    rows that have no valid rankings.
        long_counts = top_mask.sum(axis=1).replace(0, np.nan)
        long_side = top_mask.astype(float).div(long_counts, axis=0)

        if self.long_only:
            monthly_weights = long_side
        else:
            short_counts = bottom_mask.sum(axis=1).replace(0, np.nan)
            short_side = -bottom_mask.astype(float).div(short_counts, axis=0)
            monthly_weights = long_side.add(short_side, fill_value=0.0)

        monthly_weights = monthly_weights.fillna(0.0)

        # 6. Forward-fill to the daily grid.
        daily_weights = monthly_weights.reindex(prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights)
