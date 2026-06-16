"""Volatility targeting (Moreira & Muir 2017).

Reference
---------
Moreira, A. & Muir, T. (2017). Volatility-Managed Portfolios.
*Journal of Finance*, 72(4), 1611-1644. DOI: 10.1111/jofi.12513.

Scale position size inversely proportional to recent realized
volatility: weight = target_vol / realized_vol. When vol is high,
reduce exposure; when vol is low, increase exposure.

Rules
-----
For each asset:
  weight = (target_vol / realized_vol) / n_assets, capped at [0, max_leverage/n]
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class VolTargeting:
    """Volatility targeting — scale exposure to maintain constant vol."""

    name: str = "vol_targeting"
    family: str = "volatility"
    asset_classes: tuple[str, ...] = ("equity", "future", "fx", "commodity", "crypto")
    paper_doi: str = "10.1111/jofi.12513"
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        target_vol: float = 0.10,
        vol_lookback: int = 20,
        max_leverage: float = 2.0,
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
