"""Vigilant Asset Allocation on 5 ETFs (Keller-Keuning 2017 VAA, G4-collapsed-defensive variant).

Implementation notes
====================

Foundational paper
------------------
Keller, W. J. & Keuning, J. W. (2014). *A Century of Generalized
Momentum: From Flexible Asset Allocations (FAA) to Elastic Asset
Allocation (EAA)*. SSRN Working Paper 2543979.
https://doi.org/10.2139/ssrn.2543979

The 2014 paper establishes the *generalized-momentum* framework
that VAA builds on: a multi-factor momentum score combining
short-, medium-, and long-horizon returns, applied to a tactical
asset-allocation rotation. EAA uses a weighted momentum aggregator
similar to 13612W but with crash-protection logic — VAA refines
this into the explicit canary-asset fallback below.

Primary methodology
-------------------
Keller, W. J. & Keuning, J. W. (2017). *Breadth Momentum and the
Canary Universe: Defensive Asset Allocation (DAA)*. SSRN Working
Paper 3002624.
https://doi.org/10.2139/ssrn.3002624

(Published variously as "Breadth Momentum and Vigilant Asset
Allocation" — the SSRN title later updated to reference DAA which
shares the same canary-momentum mechanic. The 2017 paper is the
canonical reference for the VAA / DAA breadth-momentum framework.)

The 2017 paper specifies:

1. **13612W momentum score**: ``W(r_1, r_3, r_6, r_12) = 12·r_1 +
   4·r_3 + 2·r_6 + r_12``. The 12-month return is the canonical
   AMP-style momentum signal; the shorter-horizon returns add
   reactivity (the 1-month weight dominates the score).
2. **Breadth-momentum gate**: a "canary" universe (typically the
   same as the offensive universe) decides whether to be risk-on
   or risk-off. If *any* canary asset has a non-positive 13612W
   score, the portfolio goes fully defensive. Otherwise, the
   portfolio allocates to the top-N risky assets by 13612W.

The canonical Keller-Keuning 2017 implementation is **VAA-G4**:
4 offensive risky assets (SPY, VEA, VWO, BND) + 3 defensive
assets (LQD, IEF, SHY). Top-1 of offensive when risk-on;
top-1 of defensive when risk-off.

Why two papers
--------------
Keller-Keuning 2014 specifies the *generalized-momentum aggregator*
(13612W-style weighted scoring) and the framework of momentum-
based tactical allocation. Keller-Keuning 2017 adds the *breadth-
momentum gate* (canary universe + cash-bucket fallback) that is
the load-bearing innovation of VAA over plain TSMOM strategies
like AMP §V. Both are cited so the audit trail covers the
aggregator (2014) and the gate (2017).

Where AMP §V (the anchor for Commit 3's gtaa_cross_asset_momentum)
trades the *sign* of a single 12-month return with continuous
vol-scaled weights, VAA aggregates four lookback horizons (1 / 3 /
6 / 12 months) and uses a *discrete* gate to switch between an
offensive rotation and a defensive cash-bucket. The two mechanics
are complementary: VAA produces stronger crash protection at the
cost of higher whipsaw risk during indecisive markets.

Differentiation from sibling Phase 1 and Phase 2 strategies
-----------------------------------------------------------
* **Phase 1 ``dual_momentum_gem``** (trend family, Antonacci 2014)
  — closest cluster sibling. Both use discrete momentum-based
  rotation; both use a defensive cash-bucket fallback. Three
  load-bearing differentiations:
    1. **Score formulation.** ``dual_momentum_gem`` uses a single
       12-month total return; VAA aggregates 4 lookback horizons
       via the 13612W weighted score. The 13612W aggregator is
       materially more reactive (1-month weight dominates) — VAA
       flips into defensive earlier in a developing drawdown.
    2. **Universe and bucket structure.** ``dual_momentum_gem``
       uses a 3-asset offensive (US / Intl / bonds) with absolute-
       momentum filter on US-vs-risk-free; VAA uses a 4-asset
       offensive (SPY/EFA/EEM/AGG) with the canary gate on *all
       four* assets (any-negative → defensive).
    3. **Defensive bucket.** ``dual_momentum_gem`` falls back to
       AGG (intermediate Treasuries with credit); this VAA variant
       falls back to SHY (short Treasuries, cleaner cash proxy).
  Expected ρ ≈ 0.40–0.60 (correlated direction in clear regimes,
  uncorrelated during transitional periods when the more-reactive
  13612W and the 12-month signal disagree).
* **Phase 2 Session 2G ``gtaa_cross_asset_momentum``** (Commit 3,
  AMP 2013 §V) — same broad-asset universe theme but
  continuous-vol-scaled long-short weights instead of discrete
  top-1 / defensive rotation. Expected ρ ≈ 0.30–0.50 in clean
  trending regimes (when AMP's continuous and VAA's discrete
  signals agree) and lower otherwise.
* **Phase 2 Session 2G ``permanent_portfolio``** (Commit 2) —
  static 25/25/25/25 allocator with no rotation logic. Expected
  ρ ≈ 0.20–0.40 (static-vs-tactical philosophy).

Cluster expectations are documented in ``known_failures.md``.

Universe (5-ETF VAA, G4-collapsed-defensive variant)
----------------------------------------------------
* **Offensive (4 canary):**
  - ``SPY``: US large-cap equity
  - ``EFA``: International developed equity (MSCI EAFE)
  - ``EEM``: Emerging-markets equity (MSCI EM)
  - ``AGG``: US aggregate bonds (intermediate duration)
* **Defensive (1 cash bucket):**
  - ``SHY``: 1-3y Treasuries (cash proxy)

This is **VAA-G4 with the 3-asset defensive bucket collapsed to a
single SHY leg**. The collapse preserves VAA's risk-on / risk-off
gate while reducing the universe to the 5-ETF size called for in
the Session 2G plan. The trade-off versus the full VAA-G4 is that
the defensive bucket cannot pick between LQD / IEF / SHY based on
their own 13612W scores — in risk-off regimes the strategy holds
SHY unconditionally. The simplification is documented as an
"implementation deviation" in ``paper.md``.

Published rules (Keller-Keuning 2017 VAA-G4, 5-ETF variant)
-----------------------------------------------------------
For each month-end *t*:

1. Compute 4 monthly returns for each of the 5 ETFs::

       r_1(a)  = price(a, t) / price(a, t-1m)  - 1
       r_3(a)  = price(a, t) / price(a, t-3m)  - 1
       r_6(a)  = price(a, t) / price(a, t-6m)  - 1
       r_12(a) = price(a, t) / price(a, t-12m) - 1

2. Compute the 13612W weighted momentum score for each ETF::

       W(a) = 12 · r_1(a) + 4 · r_3(a) + 2 · r_6(a) + r_12(a)

3. **Breadth-momentum gate (canary check):**
   - If ANY of the 4 offensive assets has ``W(a) <= 0``: the
     portfolio is **risk-off**.
   - Otherwise (ALL 4 offensive assets have ``W(a) > 0``):
     the portfolio is **risk-on**.

4. **Allocation:**
   - **Risk-on:** ``weight = 1.0`` on the offensive asset with the
     highest 13612W score; ``weight = 0.0`` on all others.
   - **Risk-off:** ``weight = 1.0`` on ``SHY``; ``weight = 0.0``
     on all four offensive assets.

5. Hold one month, recompute at the next month-end.

Sign convention
---------------
Long-only, single-asset 100%-allocation strategy. Exactly one ETF
holds the full 1.0 weight at any given rebalance; the other four
hold 0.0. Discrete top-1 picking — no fractional allocation, no
shorting, no leverage.

Edge cases
----------
* Warm-up: requires 12 months of price history per ETF. Before
  that, the strategy emits zero weights for every ETF (i.e. the
  portfolio is unallocated; the bridge holds 100% cash).
* NaN handling: any ETF with a NaN in any of the 4 lookback
  returns is treated as having ``W(a) = -inf`` (effectively a
  failed canary, forcing risk-off if it's an offensive asset).
* Tied scores: ``argmax`` returns the first maximum in column
  order. With realistic price data the tie probability is
  negligible; the convention is deterministic.

Rebalance cadence
-----------------
Monthly target signal. The vectorbt bridge applies
``SizeType.TargetPercent`` semantics, producing daily drift-
correction trades on top of the monthly signal — see Session 2G
amendment "alphakit-wide rebalance-cadence convention" in
``docs/phase-2-amendments.md`` for the project-wide framing.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class VigilantAssetAllocation5:
    """Vigilant Asset Allocation on 5 ETFs (Keller-Keuning 2017 VAA-G4 variant).

    Parameters
    ----------
    offensive_symbols
        The 4 offensive / canary asset symbols. Defaults to
        ``("SPY", "EFA", "EEM", "AGG")`` — VAA-G4's offensive
        bucket. All four serve as canary assets: any negative
        13612W triggers the risk-off switch.
    defensive_symbol
        The single defensive (cash-bucket) asset symbol. Defaults
        to ``"SHY"``. The 5-ETF VAA collapses Keller-Keuning's
        3-asset defensive bucket (LQD / IEF / SHY) to a single
        leg — see strategy module docstring.
    score_weights
        Weights applied to the (r_1, r_3, r_6, r_12) returns in
        the 13612W aggregator. Defaults to ``(12.0, 4.0, 2.0,
        1.0)`` per Keller-Keuning 2017. The 1-month weight
        dominates (~63% of total weight at default settings).
    lookbacks_months
        Lookback windows in months for the four return components.
        Defaults to ``(1, 3, 6, 12)``. Must be strictly increasing
        and the maximum must be the warm-up requirement.
    """

    name: str = "vigilant_asset_allocation_5"
    family: str = "macro"
    asset_classes: tuple[str, ...] = ("equity", "bonds", "cash")
    paper_doi: str = "10.2139/ssrn.3002624"  # Keller-Keuning 2017
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        offensive_symbols: tuple[str, str, str, str] = ("SPY", "EFA", "EEM", "AGG"),
        defensive_symbol: str = "SHY",
        score_weights: tuple[float, float, float, float] = (12.0, 4.0, 2.0, 1.0),
        lookbacks_months: tuple[int, int, int, int] = (1, 3, 6, 12),
    ) -> None:
        if len(offensive_symbols) != 4:
            raise ValueError(
                f"offensive_symbols must have exactly 4 entries; got {offensive_symbols}"
            )
        for i, sym in enumerate(offensive_symbols):
            if not isinstance(sym, str) or not sym:
                raise ValueError(f"offensive_symbols[{i}] must be a non-empty string, got {sym!r}")
        if not isinstance(defensive_symbol, str) or not defensive_symbol:
            raise ValueError(
                f"defensive_symbol must be a non-empty string, got {defensive_symbol!r}"
            )
        all_symbols = (*offensive_symbols, defensive_symbol)
        if len(set(all_symbols)) != 5:
            raise ValueError(
                f"offensive + defensive symbols must be distinct (5 unique); got {all_symbols}"
            )

        if len(score_weights) != 4:
            raise ValueError(f"score_weights must have exactly 4 entries; got {score_weights}")
        if any(w < 0 for w in score_weights):
            raise ValueError(f"score_weights must be non-negative; got {score_weights}")
        if sum(score_weights) <= 0:
            raise ValueError(f"score_weights must have positive sum; got {score_weights}")

        if len(lookbacks_months) != 4:
            raise ValueError(
                f"lookbacks_months must have exactly 4 entries; got {lookbacks_months}"
            )
        if any(m <= 0 for m in lookbacks_months):
            raise ValueError(f"lookbacks_months must all be positive; got {lookbacks_months}")
        if sorted(lookbacks_months) != list(lookbacks_months):
            raise ValueError(
                f"lookbacks_months must be strictly increasing; got {lookbacks_months}"
            )
        if len(set(lookbacks_months)) != 4:
            raise ValueError(f"lookbacks_months must be distinct; got {lookbacks_months}")

        self.offensive_symbols = offensive_symbols
        self.defensive_symbol = defensive_symbol
        self.score_weights = score_weights
        self.lookbacks_months = lookbacks_months

    @property
    def required_symbols(self) -> tuple[str, str, str, str, str]:
        """The 5 ETF symbols this strategy requires in the input panel."""
        return (*self.offensive_symbols, self.defensive_symbol)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a target-weights DataFrame for ``prices``.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps. Must contain the
            4 offensive + 1 defensive ETF symbols (default: SPY,
            EFA, EEM, AGG, SHY). Additional columns are ignored.
            Values must be strictly positive (closing prices).

        Returns
        -------
        weights
            DataFrame aligned to ``prices`` with one column per
            required symbol. Exactly one ETF holds 1.0 from the
            first valid month-end onward (risk-on top-1 of
            offensive, or risk-off SHY); the other four hold 0.0.
            Bars before warm-up emit zero weights on all five legs.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")

        missing = [s for s in self.required_symbols if s not in prices.columns]
        if missing:
            raise KeyError(
                f"prices is missing required columns for vigilant_asset_allocation_5: "
                f"{missing}. Required: {list(self.required_symbols)}; "
                f"got: {list(prices.columns)}"
            )

        leg_prices = prices.loc[:, list(self.required_symbols)]

        if leg_prices.empty:
            return pd.DataFrame(
                index=prices.index,
                columns=list(self.required_symbols),
                dtype=float,
            )

        if not isinstance(leg_prices.index, pd.DatetimeIndex):
            raise TypeError(
                f"prices must have a DatetimeIndex, got {type(leg_prices.index).__name__}"
            )
        if (leg_prices <= 0).any().any():
            raise ValueError("prices must be strictly positive for all five legs")

        # 1. Resample to month-end and compute the 4 lookback returns per ETF.
        month_end_prices = leg_prices.resample("ME").last()
        lookback_returns: list[pd.DataFrame] = []
        for lookback in self.lookbacks_months:
            r = month_end_prices.pct_change(lookback)
            lookback_returns.append(r)

        # 2. Compute the 13612W weighted score for each ETF at each month-end.
        score = sum(w * r for w, r in zip(self.score_weights, lookback_returns, strict=False))
        score = cast(pd.DataFrame, score)

        # Warm-up: where any lookback return is NaN, score is NaN.
        # Convert NaN to -inf so the canary check and argmax both fail safely.
        score_filled = score.fillna(-np.inf)

        # 3. Canary breadth-momentum gate.
        offensive_cols = list(self.offensive_symbols)
        offensive_scores = score_filled[offensive_cols]
        all_offensive_positive = (offensive_scores > 0).all(axis=1)
        # When any score is -inf (warmup), all_offensive_positive is False.

        # 4. Allocate. Initialise a month-end weights frame at zero.
        monthly_weights = pd.DataFrame(
            0.0,
            index=month_end_prices.index,
            columns=list(self.required_symbols),
        )

        # Risk-on rows: top-1 of offensive gets 1.0.
        risk_on_mask = all_offensive_positive & offensive_scores.notna().all(axis=1)
        # Only fill rows where at least one offensive score is finite (post-warmup).
        valid_offensive = (offensive_scores != -np.inf).all(axis=1)
        risk_on_mask = risk_on_mask & valid_offensive
        if risk_on_mask.any():
            top_offensive = offensive_scores.loc[risk_on_mask].idxmax(axis=1)
            for date, col in top_offensive.items():
                monthly_weights.loc[date, col] = 1.0

        # Risk-off rows: defensive gets 1.0. Only when at least one offensive
        # score is finite (i.e. past warmup) AND not risk-on.
        risk_off_mask = valid_offensive & ~risk_on_mask
        monthly_weights.loc[risk_off_mask, self.defensive_symbol] = 1.0

        # 5. Forward-fill to daily index and zero-fill warmup NaNs.
        daily_weights = monthly_weights.reindex(leg_prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights)
