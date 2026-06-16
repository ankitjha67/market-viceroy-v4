"""52-week high momentum (George & Hwang 2004).

Paper
-----
George, T. J. & Hwang, C.-Y. (2004).
*The 52-week high and momentum investing*.
The Journal of Finance, 59(5), 2145–2176.
https://doi.org/10.1111/j.1540-6261.2004.00695.x

Rules
-----
1. For each stock, compute the ratio of today's price to its trailing
   52-week (252-trading-day) high.
2. At each month-end, rank stocks cross-sectionally on this ratio.
3. Go long the top decile (nearest to their 52-week high) and short
   the bottom decile (furthest from it).
4. Rebalance monthly.

Why it works (according to the authors): investors anchor on the
52-week high as a psychological reference point. When a stock
approaches that level, anchoring causes them to under-react to
further positive news, so the price grinds slowly higher rather than
jumping to fair value. The ratio is a near-sufficient statistic
for momentum that outperforms trailing-return-based momentum in
the paper's in-sample window.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

_DAYS_PER_WEEK = 5


class FiftyTwoWeekHigh:
    """52-week high momentum (George-Hwang 2004)."""

    name: str = "fifty_two_week_high"
    family: str = "trend"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1111/j.1540-6261.2004.00695.x"
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        lookback_weeks: int = 52,
        top_pct: float = 0.1,
        long_only: bool = False,
        min_positions_per_side: int = 1,
    ) -> None:
        if lookback_weeks <= 0:
            raise ValueError(f"lookback_weeks must be positive, got {lookback_weeks}")
        if not 0.0 < top_pct <= 0.5:
            raise ValueError(f"top_pct must be in (0, 0.5], got {top_pct}")
        if min_positions_per_side < 1:
            raise ValueError(f"min_positions_per_side must be >= 1, got {min_positions_per_side}")
        self.lookback_weeks = lookback_weeks
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

        window_days = self.lookback_weeks * _DAYS_PER_WEEK
        rolling_max = prices.rolling(window_days, min_periods=window_days).max()
        # Ratio of price to 52-week high ∈ (0, 1]. Close to 1 = near highs.
        ratio = prices / rolling_max

        monthly_signal = ratio.resample("ME").last()

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
