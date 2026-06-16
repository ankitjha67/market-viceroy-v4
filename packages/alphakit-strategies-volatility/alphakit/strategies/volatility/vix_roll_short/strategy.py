"""Short VIX roll yield (Alexander & Korovilas 2012).

Reference
---------
Alexander, C. & Korovilas, D. (2012). Understanding ETNs on VIX
Futures. SSRN. DOI: 10.2139/ssrn.2043061.

**WARNING**: This strategy has catastrophic tail risk (see XIV
blowup Feb 2018). Document prominently in known_failures.md.

Proxy: Long equity + scale by inverse of vol ratio. When vol is
low (contango regime), hold full position to harvest roll yield.
When vol spikes, reduce/exit.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class VIXRollShort:
    """Short VIX roll — harvest contango roll yield (XIV-style)."""

    name: str = "vix_roll_short"
    family: str = "volatility"
    asset_classes: tuple[str, ...] = ("equity", "future")
    paper_doi: str = "10.2139/ssrn.2043061"
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        vol_lookback: int = 20,
        vol_cap: float = 0.25,
        long_only: bool = False,
    ) -> None:
        if vol_lookback <= 1:
            raise ValueError(f"vol_lookback must be > 1, got {vol_lookback}")
        if vol_cap <= 0.0:
            raise ValueError(f"vol_cap must be positive, got {vol_cap}")
        self.vol_lookback = vol_lookback
        self.vol_cap = vol_cap
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

        # Full position when vol < cap; scale down when vol > cap; exit at 2x cap
        scale = (self.vol_cap / realized_vol.replace(0.0, np.nan)).clip(upper=1.0)
        # Go flat when vol > 2x cap (crisis regime)
        scale = scale.where(realized_vol <= 2 * self.vol_cap, 0.0)

        weights = scale / n
        if self.long_only:
            weights = weights.clip(lower=0.0)
        return cast(pd.DataFrame, weights.fillna(0.0))
