"""Variance risk premium harvest (Carr & Wu 2009).

Reference
---------
Carr, P. & Wu, L. (2009). Variance Risk Premia. *Review of
Financial Studies*, 22(3), 1311-1341. DOI: 10.1093/rfs/hhn038.

Harvest the variance risk premium by systematically selling
variance. Position sized by realized-vol ratio: full position when
vol is near target, scaled down when vol exceeds target.

Proxy: No options needed. Uses realized vol term structure
(slow vol > fast vol = premium present).
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class VRPHarvest:
    """VRP harvest — systematic short-variance via vol scaling."""

    name: str = "vrp_harvest"
    family: str = "volatility"
    asset_classes: tuple[str, ...] = ("equity", "future")
    paper_doi: str = "10.1093/rfs/hhn038"
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        fast_vol_window: int = 5,
        slow_vol_window: int = 60,
        target_vol: float = 0.10,
        long_only: bool = False,
    ) -> None:
        if fast_vol_window <= 1:
            raise ValueError(f"fast_vol_window must be > 1, got {fast_vol_window}")
        if slow_vol_window <= 1:
            raise ValueError(f"slow_vol_window must be > 1, got {slow_vol_window}")
        if fast_vol_window >= slow_vol_window:
            raise ValueError(
                f"fast_vol_window ({fast_vol_window}) must be < slow_vol_window ({slow_vol_window})"
            )
        if target_vol <= 0.0:
            raise ValueError(f"target_vol must be positive, got {target_vol}")
        self.fast_vol_window = fast_vol_window
        self.slow_vol_window = slow_vol_window
        self.target_vol = target_vol
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

        n = len(prices.columns)
        daily_ret = prices.pct_change()
        fast_vol = daily_ret.rolling(
            window=self.fast_vol_window, min_periods=self.fast_vol_window
        ).std(ddof=1) * np.sqrt(252)
        slow_vol = daily_ret.rolling(
            window=self.slow_vol_window, min_periods=self.slow_vol_window
        ).std(ddof=1) * np.sqrt(252)

        # VRP present when slow > fast (contango); absent when fast > slow
        vrp_signal = slow_vol - fast_vol

        # Long when VRP positive (premium available), position sized by
        # target_vol / realized_vol
        raw = (self.target_vol / fast_vol.replace(0.0, np.nan)).clip(upper=2.0)
        # Zero out when VRP is negative (backwardation = no premium)
        weights_np = np.where(vrp_signal.to_numpy() > 0, raw.to_numpy(), 0.0)
        weights = pd.DataFrame(weights_np, index=prices.index, columns=prices.columns)
        weights = weights / n

        if self.long_only:
            weights = weights.clip(lower=0.0)

        return cast(pd.DataFrame, weights.fillna(0.0))
