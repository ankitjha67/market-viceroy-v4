"""VIX term structure trading (Simon & Campasano 2014).

Reference
---------
Simon, D.P. & Campasano, J. (2014). The VIX Futures Basis.
*Journal of Trading*, 9(3), 64-74. DOI: 10.3905/jot.2014.9.3.064.

**Phase 1 proxy**: VIX proxied by trailing realized vol of SPY.
Term structure slope proxied by comparing short-term (5-day) vs
long-term (60-day) realized vol. Contango (short > long) → short
vol; backwardation (short < long) → long vol.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class VIXTermStructure:
    """VIX term structure — trade contango/backwardation proxy."""

    name: str = "vix_term_structure"
    family: str = "volatility"
    asset_classes: tuple[str, ...] = ("equity", "future")
    paper_doi: str = "10.3905/jot.2014.9.3.064"
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        short_vol_window: int = 5,
        long_vol_window: int = 60,
        long_only: bool = False,
    ) -> None:
        if short_vol_window <= 1:
            raise ValueError(f"short_vol_window must be > 1, got {short_vol_window}")
        if long_vol_window <= 1:
            raise ValueError(f"long_vol_window must be > 1, got {long_vol_window}")
        if short_vol_window >= long_vol_window:
            raise ValueError(
                f"short_vol_window ({short_vol_window}) must be < "
                f"long_vol_window ({long_vol_window})"
            )
        self.short_vol_window = short_vol_window
        self.long_vol_window = long_vol_window
        self.long_only = long_only

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        daily_ret = prices.pct_change()
        short_vol = daily_ret.rolling(
            window=self.short_vol_window, min_periods=self.short_vol_window
        ).std(ddof=1)
        long_vol = daily_ret.rolling(
            window=self.long_vol_window, min_periods=self.long_vol_window
        ).std(ddof=1)

        n = len(prices.columns)
        # Contango (long_vol > short_vol) → long equity (vol selling)
        # Backwardation (short_vol > long_vol) → short equity (vol buying)
        signal = pd.DataFrame(
            np.where(
                long_vol.to_numpy() > short_vol.to_numpy(),
                1.0,
                np.where(short_vol.to_numpy() > long_vol.to_numpy(), -1.0, 0.0),
            ),
            index=prices.index,
            columns=prices.columns,
        )
        if self.long_only:
            signal = signal.clip(lower=0.0)
        return cast(pd.DataFrame, (signal / n).fillna(0.0))
