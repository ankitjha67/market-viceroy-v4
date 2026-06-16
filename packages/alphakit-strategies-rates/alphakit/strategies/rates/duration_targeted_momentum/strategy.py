"""Cross-sectional momentum on duration-adjusted bond returns (Durham 2015).

Implementation notes
====================

Primary methodology
-------------------
Durham, J. B. (2015). *Momentum and the Term Structure of Interest
Rates*. Federal Reserve Board, Finance and Economics Discussion
Series 2015-103.
https://www.federalreserve.gov/econresdata/feds/2015/files/2015103pap.pdf

Durham documents that momentum signals on Treasury bond returns are
informative across the term structure but most reliable when the
returns are *duration-adjusted* before ranking. Without duration
adjustment, the longest-duration bond dominates the cross-sectional
ranking purely because it has the largest absolute return moves,
which is a duration exposure rather than a momentum signal.
Adjusting for duration gives each bond's return its "per-unit-of-
risk" magnitude, which is what the momentum signal is intended to
extract.

Why a single primary citation
-----------------------------
Durham (2015) is the foundational and primary reference for this
specific construction. The duration-adjusted ranking he documents
is the methodology implemented; the strategy does not draw on a
separate foundational paper because the construction is fully
specified by §III–IV of the working paper.

Differentiation from sibling momentum strategies
------------------------------------------------
* `bond_tsmom_12_1` — *single-asset* sign-of-12/1-return on a single
  bond. Uses raw price returns without duration adjustment. Trades
  outright duration when the trailing return is positive.
* `duration_targeted_momentum` (this strategy) — *cross-sectional*
  rank on duration-adjusted 12/1 returns across multiple bond
  proxies. Long the top quantile, short the bottom; weights sum to
  zero (dollar-neutral). The output is a relative-value trade across
  the bond panel rather than an outright duration position.
* `g10_bond_carry` (Session 2D Commit 11) — cross-sectional but
  ranked on *carry*, not momentum. Different signal, complementary
  trade.

Because this strategy is dollar-neutral by construction, its
expected ρ with `bond_tsmom_12_1` is moderate (0.5–0.8) when one
bond dominates the cross-section but lower when the dispersion is
concentrated mid-curve.

Published rules (Durham §III–IV)
--------------------------------
For each bond ``b`` and each month-end ``t``:

1. Compute the trailing 12-1 log return ``r_b(t)`` over months
   ``[t−12, t−1)`` (same skip-month convention as Moskowitz/Ooi/
   Pedersen 2012 and Asness 2013 §V).
2. **Duration-adjust:** divide by the bond's modified duration
   ``D_b`` to obtain the per-unit-of-duration return::

       s_b(t) = r_b(t) / D_b

   Durations are configured from the bond proxy (default 1.95 for
   SHY, 8.0 for IEF, 17.0 for TLT — values reflect the *ETF
   effective durations*, not the constant-maturity durations used
   in the curve strategies in this family).
3. **Cross-sectional rank:** at each month-end, rank ``s_b(t)``
   across the bond panel and convert to dollar-neutral weights::

       rank_b ∈ {1, ..., N}
       weight_b = (rank_b − (N+1)/2) / Σ |rank_k − (N+1)/2|

   The weights sum to zero (dollar-neutral) and each absolute weight
   is in ``[0, 1]``.
4. **Rebalance** monthly; forward-fill weights to the daily input
   index.

Edge cases
----------
* Before ``lookback_months`` months of history are available, all
  weights are zero.
* If only one bond column is provided, the strategy raises
  ``ValueError`` (cross-sectional rank requires N ≥ 2).
* Constant prices on any bond produce zero duration-adjusted return
  for that bond, which still participates in the ranking but at the
  middle of the rank distribution; this is by design and matches
  Durham's specification.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class DurationTargetedMomentum:
    """Cross-sectional momentum on duration-adjusted bond returns.

    Parameters
    ----------
    lookback_months
        Total months of history sampled (default ``12``). Inclusive
        of the skipped most-recent month.
    skip_months
        Months to skip from the most recent end (default ``1``,
        per the 12/1 convention).
    durations
        Mapping from bond column name to modified duration. The
        strategy looks up each input column's duration here at
        ``generate_signals`` time; passing prices with a column not
        in this mapping raises ``ValueError``. Defaults to
        ``{"SHY": 1.95, "IEF": 8.0, "TLT": 17.0}``.
    """

    name: str = "duration_targeted_momentum"
    family: str = "rates"
    asset_classes: tuple[str, ...] = ("bond",)
    paper_doi: str = "10.17016/FEDS.2015.103"  # Durham 2015 FEDS WP
    rebalance_frequency: str = "monthly"

    DEFAULT_DURATIONS: dict[str, float] = {  # noqa: RUF012
        "SHY": 1.95,
        "IEF": 8.0,
        "TLT": 17.0,
    }

    def __init__(
        self,
        *,
        lookback_months: int = 12,
        skip_months: int = 1,
        durations: dict[str, float] | None = None,
    ) -> None:
        if lookback_months <= 0:
            raise ValueError(f"lookback_months must be positive, got {lookback_months}")
        if skip_months < 0:
            raise ValueError(f"skip_months must be non-negative, got {skip_months}")
        if skip_months >= lookback_months:
            raise ValueError(
                f"skip_months ({skip_months}) must be < lookback_months ({lookback_months})"
            )

        self.lookback_months = lookback_months
        self.skip_months = skip_months
        self.durations = dict(self.DEFAULT_DURATIONS) if durations is None else dict(durations)
        for col, d in self.durations.items():
            if d <= 0:
                raise ValueError(f"duration for {col!r} must be positive, got {d}")

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return dollar-neutral cross-sectional weights aligned to ``prices``.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps, with each column a
            bond proxy. Every column name must be present in
            ``self.durations``.

        Returns
        -------
        weights
            Same shape as ``prices``. Each row sums to zero (dollar-
            neutral); absolute weights are in ``[0, 1]``.
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

        missing = set(prices.columns) - set(self.durations.keys())
        if missing:
            raise ValueError(
                f"durations not configured for columns: {sorted(missing)}; "
                f"add to self.durations or pass via constructor"
            )

        month_end_prices = prices.resample("ME").last()
        monthly_log_returns = np.log(month_end_prices / month_end_prices.shift(1))
        effective_window = self.lookback_months - self.skip_months
        lookback_returns = (
            monthly_log_returns.rolling(effective_window).sum().shift(self.skip_months)
        )

        durations_series = pd.Series(
            {col: self.durations[col] for col in prices.columns},
            dtype=float,
        )
        duration_adjusted = lookback_returns.divide(durations_series, axis=1)

        ranks = duration_adjusted.rank(axis=1, method="average", ascending=True)
        n = float(prices.shape[1])
        demeaned = ranks - (n + 1.0) / 2.0
        normaliser = demeaned.abs().sum(axis=1).replace(0.0, np.nan)
        monthly_weights = demeaned.div(normaliser, axis=0)

        daily_weights = monthly_weights.reindex(prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights)
