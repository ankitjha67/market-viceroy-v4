"""Cross-sectional curve-carry on a commodity-futures panel.

Implementation notes
====================

Foundational paper
------------------
Erb, C. B. & Harvey, C. R. (2006).
*The strategic and tactical value of commodity futures*.
Financial Analysts Journal, 62(2), 69–97.
https://doi.org/10.2469/faj.v62.n2.4084

Section III formalises the single-asset curve-carry rule on the
commodity panel: long backwardated, short contangoed. Single-asset
expressions are shipped as ``wti_backwardation_carry`` (long-only
WTI) and ``ng_contango_short`` (short-only NG); this strategy is
the *cross-sectional rank-based* generalisation.

Primary methodology
-------------------
Koijen, R. S. J., Moskowitz, T. J., Pedersen, L. H. & Vrugt, E. B.
(2018). *Carry*. Journal of Financial Economics, 127(2), 197–225.
https://doi.org/10.1016/j.jfineco.2017.11.002

KMPV 2018 unifies "carry" across asset classes (currencies, bonds,
equities, commodities, options) under a single signal: the return
the asset earns *if prices do not change*. For commodity futures,
that signal is the **roll yield** ``(F1 - F2) / F2`` — identical to
the EH06 §III curve slope.

Section IV (commodity-specific) applies the unified carry framework
to a commodity-futures panel and reports a long-short carry book
Sharpe of ~0.7 over 1980-2012. The book ranks all panel
constituents by roll yield, longs the top quantile and shorts the
bottom.

Differentiation from sibling carry strategies
---------------------------------------------
* ``wti_backwardation_carry`` — single-asset long-only on WTI
  specifically. ρ ≈ 0.4-0.6 (WTI is typically a large carry
  contributor).
* ``ng_contango_short`` — single-asset short-only on NG
  specifically. ρ ≈ 0.3-0.5 in summer-contango months (NG is
  typically in the short tail of the rank).
* This strategy generalises both — the single-asset expressions
  are special cases of the cross-sectional rank with a 1-asset
  universe.

Why ship both single-asset and cross-sectional
----------------------------------------------
The single-asset expressions and the cross-sectional rank capture
different practitioner allocations:

* Users who want a clean WTI / NG carry sleeve use the single-asset
  strategies (no cross-sectional dilution).
* Users who want the diversified KMPV §IV carry premium use this
  strategy (cross-sectional dispersion lifts the long-run Sharpe).

Predicted ρ between the strategies is documented in
``known_failures.md``; both are well below the master plan §10
deduplication bar (ρ > 0.95).

Curve-slope signal
------------------
For each commodity *c* at each daily observation *t*::

    roll_yield_c(t) = (F1_c(t) - F2_c(t)) / F2_c(t)

Smoothed with a rolling mean over ``smoothing_days`` trading days
(default 21 ≈ 1 month) to reduce roll-day noise.

Cross-sectional rank
--------------------
At each month-end *t*:

1. Compute the smoothed roll yield for every commodity in the
   panel.
2. Rank cross-sectionally.
3. **Long** the top ``top_quantile`` of the panel (highest roll
   yield = most-backwardated).
4. **Short** the bottom ``bottom_quantile`` (lowest roll yield =
   most-contangoed).
5. Equal-weight within each leg; the book is dollar-neutral by
   construction (long gross = short gross when ``top_quantile ==
   bottom_quantile``).

Sign convention
---------------
Output is a DataFrame with one column per **traded front symbol**
(the keys of ``front_next_map``). The next-month columns are
consumed for the curve signal but not traded. Values are in
``[-1.0, +1.0]`` and dollar-neutral by construction.

Edge cases
----------
* Commodities with NaN smoothed roll yield (insufficient history)
  are excluded from the rank. If the panel size after exclusion is
  smaller than ``min_panel_size``, all weights are zero.
* If ``top_quantile + bottom_quantile`` rounds to a panel of zero
  legs (very small universes), the book is mechanically empty.
* Non-positive prices in any column → ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pandas as pd

_DEFAULT_FRONT_NEXT_MAP: dict[str, str] = {
    "CL=F": "CL2=F",
    "NG=F": "NG2=F",
    "GC=F": "GC2=F",
    "SI=F": "SI2=F",
    "HG=F": "HG2=F",
    "ZC=F": "ZC2=F",
    "ZS=F": "ZS2=F",
    "ZW=F": "ZW2=F",
}


class CommodityCurveCarry:
    """Cross-sectional curve-carry on a commodity-futures panel.

    Long the top quantile of commodities by roll yield, short the
    bottom quantile, equal-weighted within each leg, dollar-neutral.

    Parameters
    ----------
    front_next_map
        Mapping ``{front_symbol: next_symbol}`` defining the panel
        and the curve-pairing for each commodity. Defaults to an
        8-commodity panel: CL, NG, GC, SI, HG, ZC, ZS, ZW (with the
        canonical ``"<sym>2=F"`` next-month proxies).
    top_quantile
        Fraction of the panel held long (highest roll yield).
        Defaults to ``1/3``. Must be in ``(0, 0.5]``.
    bottom_quantile
        Fraction of the panel held short (lowest roll yield).
        Defaults to ``1/3``. Must be in ``(0, 0.5]``.
    smoothing_days
        Rolling-mean window for the roll-yield signal. Defaults to
        ``21`` (~1 month of trading days).
    min_panel_size
        Minimum number of commodities (after NaN exclusion) required
        to form the rank. Below this, all weights are zero. Defaults
        to ``4``.
    """

    name: str = "commodity_curve_carry"
    family: str = "commodity"
    asset_classes: tuple[str, ...] = ("commodity",)
    paper_doi: str = "10.1016/j.jfineco.2017.11.002"  # KMPV 2018 §IV
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        front_next_map: Mapping[str, str] | None = None,
        top_quantile: float = 1.0 / 3.0,
        bottom_quantile: float = 1.0 / 3.0,
        smoothing_days: int = 21,
        min_panel_size: int = 4,
    ) -> None:
        if front_next_map is None:
            front_next_map = _DEFAULT_FRONT_NEXT_MAP
        if not front_next_map:
            raise ValueError("front_next_map must be non-empty")
        for front, nxt in front_next_map.items():
            if not front or not nxt:
                raise ValueError(
                    f"front_next_map entries must be non-empty strings; got {front!r}: {nxt!r}"
                )
            if front == nxt:
                raise ValueError(
                    f"front_next_map entry maps {front!r} to itself; front and next must differ"
                )
        if not (0.0 < top_quantile <= 0.5):
            raise ValueError(f"top_quantile must be in (0, 0.5], got {top_quantile}")
        if not (0.0 < bottom_quantile <= 0.5):
            raise ValueError(f"bottom_quantile must be in (0, 0.5], got {bottom_quantile}")
        if smoothing_days < 1:
            raise ValueError(f"smoothing_days must be >= 1, got {smoothing_days}")
        if min_panel_size < 2:
            raise ValueError(f"min_panel_size must be >= 2, got {min_panel_size}")

        self.front_next_map = dict(front_next_map)
        self.top_quantile = top_quantile
        self.bottom_quantile = bottom_quantile
        self.smoothing_days = smoothing_days
        self.min_panel_size = min_panel_size

    @property
    def front_symbols(self) -> list[str]:
        """List of traded front-month symbols (output columns)."""
        return list(self.front_next_map.keys())

    @property
    def next_symbols(self) -> list[str]:
        return list(self.front_next_map.values())

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a cross-sectional carry weights DataFrame.

        Parameters
        ----------
        prices
            DataFrame with at least the columns named in
            ``front_next_map`` (both keys and values). Index is daily,
            values are continuous-contract closing prices.

        Returns
        -------
        weights
            DataFrame indexed like ``prices``, columns are the front
            symbols (traded legs), values in ``[-1.0, +1.0]``,
            dollar-neutral.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=self.front_symbols, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        required = set(self.front_symbols) | set(self.next_symbols)
        missing = required - set(prices.columns)
        if missing:
            raise KeyError(
                f"prices is missing required columns: {sorted(missing)}; "
                f"got columns={list(prices.columns)}"
            )
        if (prices[list(required)] <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        # 1. Daily roll yield per commodity.
        roll_yields = pd.DataFrame(index=prices.index, columns=self.front_symbols, dtype=float)
        for front, nxt in self.front_next_map.items():
            roll_yields[front] = (prices[front] - prices[nxt]) / prices[nxt]

        # 2. Smooth.
        smoothed = roll_yields.rolling(self.smoothing_days).mean()

        # 3. Sample at month-ends and rank cross-sectionally.
        monthly = smoothed.resample("ME").last()
        monthly_weights = pd.DataFrame(0.0, index=monthly.index, columns=self.front_symbols)
        for date, row in monthly.iterrows():
            valid = row.dropna()
            n = len(valid)
            if n < self.min_panel_size:
                continue
            n_long = max(1, round(n * self.top_quantile))
            n_short = max(1, round(n * self.bottom_quantile))
            if n_long + n_short > n:
                # Quantiles overlap (very small panel); shrink legs.
                n_long = n // 2
                n_short = n - n_long
                if n_long == 0 or n_short == 0:
                    continue
            sorted_vals = valid.sort_values(ascending=False)
            long_legs = sorted_vals.index[:n_long]
            short_legs = sorted_vals.index[-n_short:]
            monthly_weights.loc[date, long_legs] = 1.0 / n_long
            monthly_weights.loc[date, short_legs] = -1.0 / n_short

        # 4. Forward-fill to daily index, zero pre-warmup rows.
        daily_weights = monthly_weights.reindex(prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights.astype(float))
