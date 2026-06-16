"""Residual momentum (Blitz, Huij & Martens 2011).

Paper
-----
Blitz, D., Huij, J. & Martens, M. (2011).
*Residual momentum*. Journal of Empirical Finance, 18(3), 506–521.
https://doi.org/10.1016/j.jempfin.2011.01.003

The idea
--------
Conventional cross-sectional momentum (JT 1993) ranks stocks by their
*total* returns. The winners are therefore partially just high-beta
stocks that happened to ride a strong market — a factor exposure, not
alpha. Blitz, Huij & Martens show that ranking on the **residual**
return (after factor exposure has been removed) produces:

* **Higher Sharpe** (≈2× the JT factor in their data)
* **Lower drawdown** during momentum crashes
* **Lower turnover**

Phase 1 simplification
----------------------
The paper uses Fama-French 3-factor regression residuals: each stock's
returns are regressed on market, size, and value, and the residual is
used as the signal. Implementing that faithfully requires a factor-
return data source (either Ken French's library or a locally computed
SMB/HML panel), which AlphaKit does not ship until Phase 4.

Here we implement the **market-hedged** variant: residual is the
asset's return minus the equal-weighted universe return. This is the
degenerate case of the paper's methodology when the factor model is
single-factor with β=1 for every stock. It captures roughly 60–70% of
the alpha improvement over vanilla cross-sectional momentum (see the
practitioner replications cited in ``paper.md``).

The full FF3 variant will be added as ``residual_momentum_ff3`` in
Phase 4 when the ``alphakit.data.factors`` adapter lands.

Rules
-----
1. Compute monthly returns.
2. Subtract the equal-weighted universe return to get residuals.
3. Sum residuals over ``[t - formation_months, t - skip_months)``.
4. Rank cross-sectionally; go long top ``top_pct``, short bottom
   ``top_pct``, equal-weight within each side.
5. Rebalance monthly.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class ResidualMomentum:
    """Cross-sectional residual momentum (Blitz et al. 2011)."""

    name: str = "residual_momentum"
    family: str = "trend"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.1016/j.jempfin.2011.01.003"
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        formation_months: int = 12,
        skip_months: int = 1,
        top_pct: float = 0.1,
        long_only: bool = False,
        min_positions_per_side: int = 1,
    ) -> None:
        if formation_months <= 0:
            raise ValueError(f"formation_months must be positive, got {formation_months}")
        if skip_months < 0:
            raise ValueError(f"skip_months must be non-negative, got {skip_months}")
        if skip_months >= formation_months:
            raise ValueError(
                f"skip_months ({skip_months}) must be < formation_months ({formation_months})"
            )
        if not 0.0 < top_pct <= 0.5:
            raise ValueError(f"top_pct must be in (0, 0.5], got {top_pct}")
        if min_positions_per_side < 1:
            raise ValueError(f"min_positions_per_side must be >= 1, got {min_positions_per_side}")

        self.formation_months = formation_months
        self.skip_months = skip_months
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

        # 1. Monthly returns.
        monthly_prices = prices.resample("ME").last()
        monthly_ret = monthly_prices.pct_change()

        # 2. Market-hedged residuals (equal-weighted market proxy).
        market_ret = monthly_ret.mean(axis=1)
        residuals = monthly_ret.sub(market_ret, axis=0)

        # 3. Residual momentum: sum residuals over the formation window,
        #    skipping the most recent month.
        effective_window = self.formation_months - self.skip_months
        residual_mom = residuals.rolling(effective_window).sum().shift(self.skip_months)

        # 4. Rank and build long/short masks.
        n_symbols = len(prices.columns)
        n_top = max(self.min_positions_per_side, round(n_symbols * self.top_pct))
        if n_top * 2 > n_symbols and not self.long_only:
            n_top = max(1, n_symbols // 2)

        ranks = residual_mom.rank(axis=1, ascending=False)
        valid = residual_mom.notna()
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

        # 5. Forward-fill to daily grid.
        daily_weights = monthly_weights.reindex(prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights)
