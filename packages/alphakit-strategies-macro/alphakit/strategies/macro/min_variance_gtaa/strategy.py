"""Long-only Minimum-Variance portfolio on stocks / bonds / commodities.

Second strategy in the macro family's covariance-primitive group
(Commits 5-7). Inherits the established ``_covariance`` helper
integration pattern from Commit 5's ``risk_parity_erc_3asset``;
differs only in the solver objective (minimum variance vs equal-
risk-contribution).

Implementation notes
====================

Foundational paper
------------------
Clarke, R., de Silva, H. & Thorley, S. (2006).
*Minimum-Variance Portfolios in the U.S. Equity Market*.
Journal of Portfolio Management 33(1), 10-24.
https://doi.org/10.3905/jpm.2006.661366

CST (2006) is the canonical *theoretical* reference for the long-
only minimum-variance portfolio. The paper proves that the long-
only MV portfolio has lower realised variance than the equal-
weight portfolio out-of-sample on the US equity market and
develops the constrained-optimisation framework that the
``_covariance`` helper's ``solve_min_variance_weights`` implements
(SLSQP with sum-to-1 equality + per-asset box constraints).

The 1/N-vs-MV comparison in CST §III shows that the MV portfolio
achieves the same Sharpe as equal-weight in the long-only case
but with materially lower variance — the result is that any
investor with a target volatility lower than equal-weight's
realised vol should prefer MV.

Primary methodology
-------------------
Haugen, R. A. & Baker, N. L. (1991).
*The Efficient Market Inefficiency of Capitalization-Weighted
Stock Portfolios*. Journal of Portfolio Management 17(3), 35-40.
https://doi.org/10.3905/jpm.1991.409335

HB (1991) is the *empirical* anchor for the low-volatility
anomaly that minimum-variance portfolios exploit. Haugen & Baker
document that capitalization-weighted equity indices are
*mean-variance inefficient* — a low-vol-tilted portfolio earns
the same return at lower variance. The paper precedes the
modern "low-vol anomaly" / "betting against beta" literature
(Frazzini & Pedersen 2014) by two decades and provides the
historical empirical foundation that CST 2006 formalises.

Why two papers
--------------
CST 2006 provides the *construction* — the long-only MV
optimisation framework with documented Sharpe / vol properties.
HB 1991 provides the *empirical premium* — the low-volatility
anomaly that makes MV portfolios attractive on a risk-adjusted
basis. Both are cited so the audit trail covers the theoretical
construction (CST) and the empirical anchor (HB).

The Session 2G plan's original target list pairs these two as
the canonical citations for minimum-variance GTAA. Both are
peer-reviewed JPM papers; the pair is registered in
``docs/papers/phase-2.bib``.

Differentiation from sibling strategies
---------------------------------------
* **Phase 2 Session 2G ``risk_parity_erc_3asset`` (Commit 5)** —
  closest cluster sibling in the covariance-primitive group.
  Same universe, same covariance estimator (``_covariance``
  helper). Difference: ERC objective (equal marginal risk
  contribution) vs MV objective (minimum portfolio variance).
  Expected ρ ≈ **0.55–0.75**. Both over-weight low-vol assets
  but MV is more aggressive about it — the MV solution typically
  concentrates 60-80% in the lowest-vol asset (TLT in our
  universe) while ERC bounds the concentration via the equal-
  contribution constraint.
* **Phase 2 Session 2G ``max_diversification`` (Commit 7)** —
  third member of the covariance-primitive group. Same universe,
  same helper. Expected ρ ≈ 0.55–0.75 — MV minimises portfolio
  variance, MDP maximises the diversification ratio; both
  exploit the same covariance estimator but with different
  objectives.
* **Phase 2 Session 2G ``permanent_portfolio`` (Commit 2)** —
  static 25/25/25/25 four-asset allocation. Expected ρ ≈
  0.50–0.70 (multi-asset static-ish allocator; MV is more
  concentrated than 25/25/25/25 because of the heavy bond
  tilt).
* **Phase 1 ``vol_targeting``** (volatility family) — per-asset
  inverse-vol scaling. Expected ρ ≈ 0.20–0.40.

Cluster expectations are documented in ``known_failures.md``.

Universe (3-asset minimum-variance, CST / HB three-class panel)
---------------------------------------------------------------
* ``SPY``: US large-cap equity (stocks leg)
* ``TLT``: 20+ year Treasuries (bonds leg, long duration)
* ``DBC``: Broad commodities (Invesco DB, commodities leg)

The universe matches ``risk_parity_erc_3asset`` exactly — this
is deliberate, see the strategy module docstring under "Within
Session 2G covariance-primitive group". A shared universe across
the three Session 2G covariance strategies means their pairwise
cluster correlations reflect *solver objective differences*
(ERC vs MV vs MDP), not arbitrary universe differences.

Published rules (CST 2006 / HB 1991, 3-asset implementation)
------------------------------------------------------------
For each month-end *t*:

1. Compute daily log returns over the trailing
   ``cov_window_days`` (default 252) bars.
2. Compute the rolling covariance matrix ``Σ_t`` via
   ``_covariance.rolling_covariance(returns, window, shrinkage)``.
   Default shrinkage is Ledoit-Wolf 2004.
3. Solve the long-only minimum-variance weights via
   ``_covariance.solve_min_variance_weights(Σ_t,
   long_only=True, max_weight=1.0)``. The solver uses SciPy
   SLSQP with sum-to-1 equality and per-asset box constraints
   ``0 ≤ w_i ≤ max_weight``.
4. Apply weights at the month-end rebalance bar; forward-fill
   to daily until the next rebalance.

Sign convention
---------------
Long-only, weights sum to 1.0. The long-only constraint may bind
at zero for high-vol assets when the unconstrained MV solution
would short them — see ``known_failures.md`` item 3 for the
binding-constraint analysis. Strategy emits zero weights on all
legs during warm-up (before ``cov_window_days`` of history are
available).

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
  asset. Before that, the strategy emits zero weights for every
  asset (the bridge holds 100% cash).
* Missing required columns: ``KeyError`` listing the missing
  symbols.
* Non-positive prices: ``ValueError``.
* Degenerate covariance: the ``_covariance.solve_min_variance_weights``
  solver raises ``ValueError`` if the SLSQP optimiser fails to
  converge. This propagates as a zero-weight emission for the
  affected rebalance (the bridge holds 100% cash).
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
from alphakit.strategies.macro._covariance import (
    ShrinkageMethod,
    rolling_covariance,
    solve_min_variance_weights,
)


class MinVarianceGtaa:
    """Long-only Minimum-Variance portfolio on stocks / bonds / commodities.

    Parameters
    ----------
    stocks_symbol
        Symbol for the stocks leg. Defaults to ``"SPY"`` (US
        large-cap equity).
    bonds_symbol
        Symbol for the bonds leg. Defaults to ``"TLT"`` (20+ year
        Treasuries — same choice as risk_parity_erc_3asset; see
        that strategy's docstring for the TLT-vs-AGG rationale).
    commodities_symbol
        Symbol for the commodities leg. Defaults to ``"DBC"``
        (Invesco DB broad-commodity ETF).
    cov_window_days
        Rolling window in trading days for the covariance estimator.
        Defaults to ``252`` (one trading year). Must be at least 60.
    shrinkage
        Covariance shrinkage method: ``"none"``, ``"ledoit_wolf"``
        (default), or ``"constant"``.
    max_weight
        Per-asset upper bound on the long-only weight. Defaults to
        ``1.0`` (no concentration cap). Set lower (e.g. ``0.6``)
        to prevent the MV solution from concentrating heavily in
        the lowest-vol asset.
    """

    name: str = "min_variance_gtaa"
    family: str = "macro"
    asset_classes: tuple[str, ...] = ("equity", "bonds", "commodities")
    paper_doi: str = "10.3905/jpm.1991.409335"  # Haugen & Baker 1991
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
        """Return long-only minimum-variance weights for ``prices``.

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
            ``_covariance.solve_min_variance_weights`` on the
            rolling covariance, forward-filled daily. All weights
            are non-negative and sum to 1.0 after warm-up; zero
            on every leg during warm-up.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")

        missing = [s for s in self.required_symbols if s not in prices.columns]
        if missing:
            raise KeyError(
                f"prices is missing required columns for min_variance_gtaa: {missing}. "
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
                w = solve_min_variance_weights(
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
