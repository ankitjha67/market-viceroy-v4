"""Short strangle proxy (Israelov & Nielsen 2014).

**SEVERE DEVIATION — _proxy suffix applies (ADR-002).**
This is NOT an options strategy. It approximates options selling
via a realized-vol-scaled equity overlay. The canonical slug
(without _proxy) is reserved for Phase 4 with real options engine.

Proxy: Long equity, scaled by (target_vol / realized_vol), capped
at max_leverage. When realized vol is low, position is larger
(selling vol is profitable). When vol spikes, position shrinks.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class ShortStrangleProxy:
    """ShortStrangleProxy — vol-selling proxy via realized-vol overlay."""

    name: str = "short_strangle_proxy"
    family: str = "volatility"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.2469/faj.v70.n6.3"
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        target_vol: float = 0.10,
        vol_lookback: int = 20,
        max_leverage: float = 1.5,
        long_only: bool = False,
    ) -> None:
        if target_vol <= 0.0:
            raise ValueError(f"target_vol must be positive, got {target_vol}")
        if vol_lookback <= 1:
            raise ValueError(f"vol_lookback must be > 1, got {vol_lookback}")
        if max_leverage <= 0.0:
            raise ValueError(f"max_leverage must be positive, got {max_leverage}")
        self.target_vol = target_vol
        self.vol_lookback = vol_lookback
        self.max_leverage = max_leverage
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
        realized_vol = daily_ret.rolling(
            window=self.vol_lookback, min_periods=self.vol_lookback
        ).std(ddof=1) * np.sqrt(252)

        raw_weight = self.target_vol / realized_vol.replace(0.0, np.nan)
        capped = raw_weight.clip(upper=self.max_leverage)
        weights = capped / n

        if self.long_only:
            weights = weights.clip(lower=0.0)

        return cast(pd.DataFrame, weights.fillna(0.0))
