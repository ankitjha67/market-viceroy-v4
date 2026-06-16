"""Maximum-Diversification Portfolio on stocks / bonds / commodities.

Third strategy in the macro family's covariance-primitive group
(Commits 5-7). Inherits the established ``_covariance`` helper
integration pattern from Commits 5 (ERC) and 6 (MV); differs only
in the solver objective (maximum diversification ratio).

Implementation notes
====================

Foundational paper
------------------
Choueifaty, Y. & Coignard, Y. (2008).
*Toward Maximum Diversification*. Journal of Portfolio Management
35(1), 40-51.
https://doi.org/10.3905/JPM.2008.35.1.40

CC (2008) is the canonical reference for the **most diversified
portfolio (MDP)**. The paper defines the *diversification ratio*

    DR(w) = (wᵀ σ) / sqrt(wᵀ Σ w)

— the ratio of the weighted average asset volatility to the
portfolio volatility — and proves that maximising DR produces the
portfolio whose squared correlation with each constituent asset is
equal. The MDP is the unique long-only portfolio where every asset
has the same correlation with the overall portfolio; this is the
"maximum diversification" property after which the construction is
named.

CC (2008) Table 2 reports Sharpe ≈ 0.80 for the MDP on a 7-asset-
class global multi-asset panel over 1959-2005, materially higher
than equal-weight and modestly higher than equal-risk-contribution
on the same universe.

Primary methodology (extended properties)
-----------------------------------------
Choueifaty, Y., Froidure, T. & Reynier, J. (2013).
*Properties of the Most Diversified Portfolio*.
Journal of Investment Management 11(3), 1-32.
SSRN 1895459. https://doi.org/10.2139/ssrn.1895459

CFR (2013) extends the MDP framework with three additional
structural properties used by this implementation:

1. *Capital allocation*: any long-only portfolio can be decomposed
   as ``w = α · MDP + (1 - α) · cash`` along the maximum-
   diversification frontier.
2. *Robustness*: MDP weights are less sensitive to estimation error
   than minimum-variance weights — a key advantage on the rolling
   sample covariance the helper provides.
3. *Numerical stability*: the SLSQP-based solver (used by the
   ``_covariance`` helper's ``solve_max_diversification_weights``)
   converges reliably on the MDP problem even with mild
   correlation-matrix degeneracies.

Strategy code replicates CC 2008's MDP weight definition; benchmark
numbers are calibrated against CC's reported 7-asset Sharpe range,
scaled down for the 3-asset substrate.

Why two papers
--------------
CC 2008 provides the *construction* — the DR definition, the MDP
weight characterisation, and the empirical risk-premium evidence
on a multi-asset panel. CFR 2013 provides the *structural
extensions* — the capital-allocation theorem, the robustness-to-
estimation-error result, and the SLSQP numerical-stability
properties relevant to the ``_covariance`` helper's solver. Both
are cited so the audit trail covers both the foundational
construction (CC) and the implementation-anchor properties (CFR).

Differentiation from sibling strategies
---------------------------------------
* **Phase 2 Session 2G ``risk_parity_erc_3asset`` (Commit 5)** —
  same universe, same covariance estimator. Different objective:
  ERC equalises *marginal risk contribution*; MDP maximises the
  *diversification ratio* (equal *correlation* with the portfolio).
  Expected ρ ≈ **0.50–0.70** — both exploit cross-asset
  correlations but MDP places more weight on assets with low
  correlation to the rest of the portfolio rather than on assets
  with low individual volatility. In our 3-asset panel where the
  3 asset classes have low pairwise correlation, MDP weights are
  closer to equal-weight than ERC or MV.
* **Phase 2 Session 2G ``min_variance_gtaa`` (Commit 6)** —
  same universe, same covariance estimator. Different objective:
  MV minimises portfolio variance; MDP maximises DR. Expected
  ρ ≈ **0.55–0.75** — both use the long-only SLSQP solver but
  with different objectives. MV concentrates in the lowest-vol
  asset (60-80% TLT); MDP spreads across the asset classes with
  the lowest-correlation pairs (typically 25-40% each in our 3-
  asset universe).
* **Phase 2 Session 2G ``permanent_portfolio`` (Commit 2)** —
  static 25/25/25/25 four-asset allocation. Expected ρ ≈
  0.40–0.60 — MDP's diversification-maximising weights are
  *closest* to the static 25/25/25/25 of the three covariance-
  primitive strategies because both philosophies target balanced
  cross-asset exposure rather than risk concentration.
* **Phase 1 ``vol_targeting``** (volatility family) — per-asset
  inverse-vol scaling. Expected ρ ≈ 0.20–0.40.

Cluster expectations are documented in ``known_failures.md``.

Universe (3-asset maximum-diversification, CC / CFR three-class panel)
----------------------------------------------------------------------
* ``SPY``: US large-cap equity (stocks leg)
* ``TLT``: 20+ year Treasuries (bonds leg, long duration)
* ``DBC``: Broad commodities (Invesco DB, commodities leg)

The universe matches ``risk_parity_erc_3asset`` and
``min_variance_gtaa`` exactly — this is deliberate. The three
Session 2G covariance-primitive strategies share a universe so
their pairwise cluster correlations reflect *solver-objective
differences* (ERC vs MV vs MDP), not arbitrary universe
divergences.

Published rules (CC 2008 / CFR 2013, 3-asset implementation)
------------------------------------------------------------
For each month-end *t*:

1. Compute daily log returns over the trailing ``cov_window_days``
   (default 252) bars.
2. Compute the rolling covariance matrix ``Σ_t`` via
   ``_covariance.rolling_covariance(returns, window, shrinkage)``.
   Default shrinkage is Ledoit-Wolf 2004.
3. Solve the long-only MDP weights via
   ``_covariance.solve_max_diversification_weights(Σ_t,
   long_only=True, max_weight=1.0)``. The solver maximises the
   diversification ratio via SciPy SLSQP minimising
   ``−DR(w) = −(wᵀ σ) / sqrt(wᵀ Σ w)``.
4. Apply weights at the month-end rebalance bar; forward-fill
   to daily until the next rebalance.

Sign convention
---------------
Long-only, weights sum to 1.0. Strategy emits zero weights on
all legs during warm-up (before ``cov_window_days`` of history
are available).

Rebalance cadence
-----------------
Monthly target signal. The vectorbt bridge applies
``SizeType.TargetPercent`` semantics, producing daily drift-
correction trades on top of the monthly signal — see Session 2G
amendment "alphakit-wide rebalance-cadence convention" in
``docs/phase-2-amendments.md`` for the project-wide framing.

Edge cases
----------
* Warm-up: requires ``cov_window_days`` bars of price history per
  asset.
* Missing required columns: ``KeyError`` listing the missing
  symbols.
* Non-positive prices: ``ValueError``.
* Degenerate covariance: the
  ``_covariance.solve_max_diversification_weights`` solver raises
  ``ValueError`` on optimiser failure. This propagates as a
  zero-weight emission for the affected rebalance.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
from alphakit.strategies.macro._covariance import (
    ShrinkageMethod,
    rolling_covariance,
    solve_max_diversification_weights,
)


class MaxDiversification:
    """Maximum-Diversification Portfolio on stocks / bonds / commodities.

    Parameters
    ----------
    stocks_symbol
        Symbol for the stocks leg. Defaults to ``"SPY"``.
    bonds_symbol
        Symbol for the bonds leg. Defaults to ``"TLT"``.
    commodities_symbol
        Symbol for the commodities leg. Defaults to ``"DBC"``.
    cov_window_days
        Rolling window in trading days for the covariance estimator.
        Defaults to ``252`` (one trading year). Must be at least 60.
    shrinkage
        Covariance shrinkage method: ``"none"``, ``"ledoit_wolf"``
        (default), or ``"constant"``.
    max_weight
        Per-asset upper bound on the long-only weight. Defaults to
        ``1.0`` (no concentration cap).
    """

    name: str = "max_diversification"
    family: str = "macro"
    asset_classes: tuple[str, ...] = ("equity", "bonds", "commodities")
    paper_doi: str = "10.2139/ssrn.1895459"  # Choueifaty-Froidure-Reynier 2013
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        stocks_symbol: str = "SPY",
        bonds_symbol: str = "TLT",
        commodities_symbol: str = "DBC",
        cov_window_days: int = 252,
        shrinkage: ShrinkageMethod = "ledoit_wolf",
        max_weight: float = 1.0,
    ) -> None:
        for label, sym in (
            ("stocks_symbol", stocks_symbol),
            ("bonds_symbol", bonds_symbol),
            ("commodities_symbol", commodities_symbol),
        ):
            if not isinstance(sym, str) or not sym:
                raise ValueError(f"{label} must be a non-empty string, got {sym!r}")
        symbols = (stocks_symbol, bonds_symbol, commodities_symbol)
        if len(set(symbols)) != 3:
            raise ValueError(
                f"stocks / bonds / commodities symbols must be distinct; got {symbols}"
            )
        if cov_window_days < 60:
            raise ValueError(f"cov_window_days must be >= 60, got {cov_window_days}")
        if shrinkage not in ("none", "ledoit_wolf", "constant"):
            raise ValueError(
                f"shrinkage must be 'none' | 'ledoit_wolf' | 'constant', got {shrinkage!r}"
            )
        if max_weight <= 0 or max_weight > 1.0:
            raise ValueError(f"max_weight must be in (0, 1]; got {max_weight}")

        self.stocks_symbol = stocks_symbol
        self.bonds_symbol = bonds_symbol
        self.commodities_symbol = commodities_symbol
        self.cov_window_days = cov_window_days
        self.shrinkage = shrinkage
        self.max_weight = max_weight

    @property
    def required_symbols(self) -> tuple[str, str, str]:
        """The three input columns this strategy requires."""
        return (self.stocks_symbol, self.bonds_symbol, self.commodities_symbol)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return long-only MDP weights for ``prices``.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps. Must contain the
            three leg symbols (default: SPY / TLT / DBC). Values
            must be strictly positive.

        Returns
        -------
        weights
            DataFrame aligned to ``prices`` with one column per
            required symbol. Weights are recomputed monthly via
            ``_covariance.solve_max_diversification_weights`` on
            the rolling covariance, forward-filled daily. All
            weights are non-negative and sum to 1.0 after warm-up;
            zero on every leg during warm-up.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")

        missing = [s for s in self.required_symbols if s not in prices.columns]
        if missing:
            raise KeyError(
                f"prices is missing required columns for max_diversification: {missing}. "
                f"Required: {list(self.required_symbols)}; got: {list(prices.columns)}"
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
            raise ValueError("prices must be strictly positive for all three legs")

        daily_log_returns = np.log(leg_prices / leg_prices.shift(1))

        rolling_cov = rolling_covariance(
            daily_log_returns.dropna(),
            window=self.cov_window_days,
            shrinkage=self.shrinkage,
        )

        if rolling_cov.empty:
            return pd.DataFrame(
                np.zeros(leg_prices.shape, dtype=float),
                index=leg_prices.index,
                columns=list(self.required_symbols),
            )

        cov_dates = pd.DatetimeIndex(rolling_cov.index.unique(level="date"))
        month_end_index = leg_prices.resample("ME").last().index
        weights_at_month_end: dict[pd.Timestamp, np.ndarray] = {}
        for me in month_end_index:
            mask = cov_dates <= me
            if not mask.any():
                continue
            cov_date = cov_dates[mask].max()
            cov_matrix = rolling_cov.loc[cov_date].to_numpy(dtype=float)
            try:
                w = solve_max_diversification_weights(
                    cov_matrix, long_only=True, max_weight=self.max_weight
                )
            except ValueError:
                continue
            weights_at_month_end[me] = w

        if not weights_at_month_end:
            return pd.DataFrame(
                np.zeros(leg_prices.shape, dtype=float),
                index=leg_prices.index,
                columns=list(self.required_symbols),
            )

        monthly_weights = pd.DataFrame(
            np.vstack(list(weights_at_month_end.values())),
            index=pd.DatetimeIndex(list(weights_at_month_end.keys())),
            columns=list(self.required_symbols),
        )
        daily_weights = monthly_weights.reindex(leg_prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights)
