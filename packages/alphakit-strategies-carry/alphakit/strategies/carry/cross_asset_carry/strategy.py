"""Cross-asset carry portfolio (KMPV 2018).

Reference
---------
Koijen, R.S.J., Moskowitz, T.J., Pedersen, L.H. & Vrugt, E.B.
(2018). Carry. *Journal of Financial Economics*, 127(2), 197-225.
DOI: 10.1016/j.jfineco.2017.11.002.

KMPV construct a diversified carry portfolio by aggregating carry
signals across asset classes (FX, equity, bonds, commodities) with
equal risk weighting. The cross-asset carry factor has a higher
Sharpe ratio than any single-asset-class carry portfolio due to
diversification.

**Phase 1 proxy**: This implementation treats the input universe
as a multi-asset panel and applies the same cross-sectional carry
ranking (trailing return proxy) across all assets. In production,
each sleeve would use asset-class-specific carry signals weighted
by inverse volatility. See ADR-001.

Rules
-----
Cross-sectional across all assets:
  1. Compute carry proxy (trailing return) per asset
  2. Risk-adjust: divide proxy by trailing volatility
  3. Rank cross-sectionally
  4. Dollar-neutral long/short
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class CrossAssetCarry:
    """Cross-asset carry — multi-asset carry aggregation (KMPV 2018)."""

    name: str = "cross_asset_carry"
    family: str = "carry"
    asset_classes: tuple[str, ...] = ("equity", "future", "fx", "commodity", "crypto")
    paper_doi: str = "10.1016/j.jfineco.2017.11.002"  # KMPV (2018)
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        lookback: int = 63,
        vol_lookback: int = 63,
        long_only: bool = False,
    ) -> None:
        if lookback <= 0:
            raise ValueError(f"lookback must be positive, got {lookback}")
        if vol_lookback <= 1:
            raise ValueError(f"vol_lookback must be > 1, got {vol_lookback}")
        self.lookback = lookback
        self.vol_lookback = vol_lookback
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

        n_assets = len(prices.columns)
        if n_assets < 2:
            return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

        # Risk-adjusted carry proxy
        trailing_ret = prices.pct_change(periods=self.lookback)
        daily_ret = prices.pct_change()
        trailing_vol = daily_ret.rolling(
            window=self.vol_lookback, min_periods=self.vol_lookback
        ).std(ddof=1)

        # Carry signal: risk-adjusted trailing return
        carry_signal = trailing_ret / trailing_vol.replace(0.0, np.nan)

        ranks = carry_signal.rank(axis=1, method="average", ascending=True)
        rank_mean = ranks.mean(axis=1)
        demeaned = ranks.sub(rank_mean, axis=0)
        abs_sum = demeaned.abs().sum(axis=1).replace(0.0, np.nan)
        weights = demeaned.div(abs_sum, axis=0)

        if self.long_only:
            weights = weights.clip(lower=0.0)
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
