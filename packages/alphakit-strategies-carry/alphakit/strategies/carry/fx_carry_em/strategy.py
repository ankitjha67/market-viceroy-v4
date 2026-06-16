"""FX carry trade — emerging markets (Burnside et al. 2011).

Reference
---------
Burnside, C., Eichenbaum, M., Kleshchelski, I. & Rebelo, S. (2011).
Do Peso Problems Explain the Returns to the Carry Trade? *Review of
Financial Studies*, 24(3), 853-891. DOI: 10.1093/rfs/hhq138.

Same logic as G10 carry but on EM currency universe. EM carry tends
to have higher absolute yields and fatter crash tails.

**Phase 1 proxy**: Trailing return as carry proxy (see ADR-001).

Rules
-----
Cross-sectional:
  1. Trailing N-day return as carry proxy
  2. Rank EM currencies by proxy
  3. Long top K, short bottom K
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class FXCarryEM:
    """FX carry trade — EM currencies, long high-yielders, short low-yielders."""

    name: str = "fx_carry_em"
    family: str = "carry"
    asset_classes: tuple[str, ...] = ("fx",)
    paper_doi: str = "10.1093/rfs/hhq138"  # Burnside et al. (2011)
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        lookback: int = 63,
        n_long: int = 3,
        n_short: int = 3,
        long_only: bool = False,
    ) -> None:
        if lookback <= 0:
            raise ValueError(f"lookback must be positive, got {lookback}")
        if n_long <= 0:
            raise ValueError(f"n_long must be positive, got {n_long}")
        if n_short <= 0:
            raise ValueError(f"n_short must be positive, got {n_short}")
        self.lookback = lookback
        self.n_long = n_long
        self.n_short = n_short
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

        n_long = min(self.n_long, n_assets // 2)
        n_short = min(self.n_short, n_assets // 2)

        carry_proxy = prices.pct_change(periods=self.lookback)
        ranks = carry_proxy.rank(axis=1, method="average", ascending=True)

        weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

        for t in range(len(prices)):
            row_ranks = ranks.iloc[t]
            if row_ranks.isna().all():
                continue
            valid = row_ranks.dropna()
            if len(valid) < 2:
                continue
            sorted_idx = valid.sort_values()
            short_syms = sorted_idx.index[:n_short]
            long_syms = sorted_idx.index[-n_long:]
            if not self.long_only:
                for sym in short_syms:
                    weights.at[prices.index[t], sym] = -1.0 / n_short
            for sym in long_syms:
                weights.at[prices.index[t], sym] = 1.0 / n_long

        if self.long_only:
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
