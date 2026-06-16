"""G10 cross-country sovereign bond carry (Asness/Moskowitz/Pedersen 2013 §V).

Implementation notes
====================

Primary methodology
-------------------
Asness, C. S., Moskowitz, T. J. & Pedersen, L. H. (2013).
*Value and momentum everywhere*. Journal of Finance, 68(3), 929–985.
Section V documents both *time-series* and *cross-sectional* carry
on sovereign bonds across G10 markets. The cross-sectional bond
carry sleeve ranks countries by their bond carry (yield level minus
short-rate, equivalently the trailing return of a constant-maturity
bond) and goes long the top quantile, short the bottom.
https://doi.org/10.1111/jofi.12021

Why a single primary citation
-----------------------------
Asness §V specifies the cross-sectional carry rule directly. KMPV
(2018) generalises the carry definition across asset classes, but
for the *bond* sleeve the methodology is identical. We anchor on
Asness 2013 because it is the simpler bond-specific reference.

Differentiation from sibling carry strategies
---------------------------------------------
* **`bond_carry_roll`** (Phase 1 carry family) — cross-sectional
  carry on a US-centric bond panel (multiple US bond indices).
  This *rates-family* strategy is the *G10-cross-country* version
  of the same mechanic. The two trade orthogonal information
  (US-only vs cross-country dispersion) and are both shipped.
* **`bond_carry_rolldown`** (this family, Commit 6) — *time-series*
  duration overlay on a single bond conditional on the slope.
  Different signal type (single-asset binary), different mechanic.

Algorithm
---------
For each month-end ``t`` and bond panel of ``N`` country bond
proxies:

1. **Trailing carry proxy:** the n-day cumulative return on each
   country's bond series. For a constant-duration bond proxy, the
   trailing return is approximately ``coupon × n − duration × Δyield``,
   which is dominated by the coupon (level) when ``Δyield`` is
   small. Bonds with higher trailing returns are typically those
   with higher yield levels — i.e. higher carry.
2. **Cross-sectional rank** of the carry proxy across countries.
3. **Dollar-neutral weights** via the demeaned-rank construction
   (long top quantile, short bottom; weights sum to zero).
4. **Forward-fill** monthly weights to daily.

Currency-hedging caveat
-----------------------
G10 cross-country bond carry returns can be either *unhedged* (in
local currency, exposes to FX) or *FX-hedged* (the canonical AMP
2013 §V version). This implementation operates on whatever bond
price series are passed in — so:

* If the input is *USD-denominated* unhedged (e.g. BWX), the
  strategy includes implicit FX exposure.
* If the input is *FX-hedged* USD-equivalent prices (constructed
  via FX forwards), the strategy isolates pure rate carry per AMP
  2013 §V.

Real-feed Session 2H benchmarks should construct the FX-hedged
return series for fidelity to the paper. Documented in
``known_failures.md``.

Per-country duration normalisation
----------------------------------
Different countries have different sovereign-bond duration profiles
(US 10Y duration ≈ 8.0; Japan 10Y ≈ 9.5 due to lower yield;
Germany 10Y ≈ 8.8). Without normalisation, low-yield-country bonds
have inflated trailing returns from the *duration* component rather
than the carry component. The strategy exposes a ``durations`` map
analogous to ``duration_targeted_momentum``; if provided, the carry
proxy is divided by per-country duration before ranking.

Edge cases
----------
* Before ``lookback_months`` months are available, all weights are
  zero.
* If ``durations`` is set but doesn't cover every input column,
  ``ValueError``.
* If only one bond is provided, ``ValueError`` (cross-sectional
  rank requires ``N >= 2``).
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class G10BondCarry:
    """G10 cross-country sovereign bond carry — long-short cross-sectional rank.

    Parameters
    ----------
    lookback_months
        Trailing window for the carry proxy (default ``3`` months —
        Asness §V uses a short window because carry is a slow-moving
        macro variable).
    durations
        Optional mapping from bond column name to modified duration.
        If provided, the carry proxy is divided by per-country
        duration before ranking. If ``None`` (default), the strategy
        uses raw trailing returns as the carry proxy and assumes
        roughly equal durations across the panel.
    """

    name: str = "g10_bond_carry"
    family: str = "rates"
    asset_classes: tuple[str, ...] = ("bond",)
    paper_doi: str = "10.1111/jofi.12021"  # Asness/Moskowitz/Pedersen 2013 §V
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        lookback_months: int = 3,
        durations: dict[str, float] | None = None,
    ) -> None:
        if lookback_months <= 0:
            raise ValueError(f"lookback_months must be positive, got {lookback_months}")
        self.lookback_months = lookback_months
        self.durations = None if durations is None else dict(durations)
        if self.durations is not None:
            for col, d in self.durations.items():
                if d <= 0:
                    raise ValueError(f"duration for {col!r} must be positive, got {d}")

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return dollar-neutral cross-sectional carry weights.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps, with each column a
            sovereign bond proxy from a different country.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if prices.shape[1] < 2:
            raise ValueError(
                f"cross-sectional rank requires >= 2 bond columns, got {prices.shape[1]}"
            )
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        if self.durations is not None:
            missing = set(prices.columns) - set(self.durations.keys())
            if missing:
                raise ValueError(
                    f"durations not configured for columns: {sorted(missing)}; "
                    f"add to self.durations or omit the argument"
                )

        month_end_prices = prices.resample("ME").last()
        monthly_log_returns = np.log(month_end_prices / month_end_prices.shift(1))
        carry_proxy = monthly_log_returns.rolling(self.lookback_months).sum()

        if self.durations is not None:
            durations_series = pd.Series(
                {col: self.durations[col] for col in prices.columns},
                dtype=float,
            )
            carry_proxy = carry_proxy.divide(durations_series, axis=1)

        ranks = carry_proxy.rank(axis=1, method="average", ascending=True)
        n = float(prices.shape[1])
        demeaned = ranks - (n + 1.0) / 2.0
        normaliser = demeaned.abs().sum(axis=1).replace(0.0, np.nan)
        monthly_weights = demeaned.div(normaliser, axis=0)

        daily_weights = monthly_weights.reindex(prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights)
