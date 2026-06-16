"""FX carry trade — G10 currencies (Lustig, Roussanov & Verdelhan 2011).

Reference
---------
Lustig, H., Roussanov, N. & Verdelhan, A. (2011). Common Risk
Factors in Currency Markets. *Review of Financial Studies*, 24(11),
3731-3777. DOI: 10.1093/rfs/hhr068.

The FX carry trade goes long high-yielding currencies and short
low-yielding currencies, earning the interest-rate differential.
Lustig et al. show that a single "carry factor" explains most of
the cross-sectional variation in currency returns.

**Phase 1 proxy**: Since the StrategyProtocol provides only close
prices (no interest-rate feeds), this implementation uses the
trailing N-day return as a proxy for the carry signal. Currencies
with positive recent returns are treated as "high carry" and vice
versa. This is a known simplification documented in ADR-001. In
production, replace with actual interest-rate differentials.

Rules
-----
Cross-sectional:
  1. Compute trailing N-day return for each currency pair
  2. Rank currencies: highest return → highest carry proxy
  3. Long top K currencies, short bottom K, equal-weight
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class FXCarryG10:
    """FX carry trade — G10 currencies, long high-yielders, short low-yielders."""

    name: str = "fx_carry_g10"
    family: str = "carry"
    asset_classes: tuple[str, ...] = ("fx",)
    paper_doi: str = "10.1093/rfs/hhr068"  # Lustig, Roussanov & Verdelhan (2011)
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

        # Carry proxy: trailing return
        carry_proxy = prices.pct_change(periods=self.lookback)

        # Rank: highest carry → highest rank
        ranks = carry_proxy.rank(axis=1, method="average", ascending=True)

        weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

        for t in range(len(prices)):
            row_ranks = ranks.iloc[t]
            if row_ranks.isna().all():
                continue

            valid = row_ranks.dropna()
            if len(valid) < 2:
                continue

            # Top n_long → long, bottom n_short → short
            sorted_idx = valid.sort_values()
            short_syms = sorted_idx.index[:n_short]
            long_syms = sorted_idx.index[-n_long:]

            if not self.long_only:
                for sym in short_syms:
                    weights.at[prices.index[t], sym] = -1.0 / n_short
            for sym in long_syms:
                w = 1.0 / n_long
                weights.at[prices.index[t], sym] = w

        # Normalize so |sum of weights| is bounded
        if self.long_only:
            row_sum = weights.sum(axis=1).replace(0.0, np.nan)
            weights = weights.div(row_sum, axis=0)

        return cast(pd.DataFrame, weights.fillna(0.0))
