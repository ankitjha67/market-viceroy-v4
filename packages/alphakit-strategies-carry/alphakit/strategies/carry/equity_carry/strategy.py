"""Equity carry (Koijen, Moskowitz, Pedersen & Vrugt 2018).

Reference
---------
Koijen, R.S.J., Moskowitz, T.J., Pedersen, L.H. & Vrugt, E.B.
(2018). Carry. *Journal of Financial Economics*, 127(2), 197-225.
DOI: 10.1016/j.jfineco.2017.11.002.

KMPV define equity carry as the expected total return from holding
an asset: dividend yield + expected buyback yield + expected price
appreciation from earnings growth. The strategy ranks equities by
carry and goes long high-carry, short low-carry.

**Phase 1 proxy**: Uses trailing return minus trailing volatility
as carry proxy (similar to dividend yield but without the vol
adjustment in the numerator). See ADR-001.

Rules
-----
Cross-sectional:
  1. Carry proxy per asset
  2. Rank and demean cross-sectionally
  3. Dollar-neutral portfolio
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class EquityCarry:
    """Equity carry — KMPV cross-sectional carry ranking."""

    name: str = "equity_carry"
    family: str = "carry"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1016/j.jfineco.2017.11.002"  # KMPV (2018)
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        lookback: int = 252,
        long_only: bool = False,
    ) -> None:
        if lookback <= 0:
            raise ValueError(f"lookback must be positive, got {lookback}")
        self.lookback = lookback
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

        # KMPV carry proxy: trailing annualized return
        trailing_ret = prices.pct_change(periods=self.lookback)

        ranks = trailing_ret.rank(axis=1, method="average", ascending=True)
        rank_mean = ranks.mean(axis=1)
        demeaned = ranks.sub(rank_mean, axis=0)
        abs_sum = demeaned.abs().sum(axis=1).replace(0.0, np.nan)
        weights = demeaned.div(abs_sum, axis=0)

        if self.long_only:
            weights = weights.clip(lower=0.0)
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
