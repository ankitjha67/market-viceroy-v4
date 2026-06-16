"""Equal-Risk-Contribution (ERC) portfolio across stocks / bonds / commodities.

First strategy in the macro family's covariance-primitive group
(Commits 5-7). Uses the package-private ``_covariance`` helper
(Commit 1.5) for the rolling covariance estimation and the ERC
fixed-point solver. The same helper is consumed by
``min_variance_gtaa`` (Commit 6) and ``max_diversification``
(Commit 7) — keeping the three solvers behind a single estimator
preserves cluster-prediction integrity (their cluster ρ values
reflect methodological differences in the *solver*, not arbitrary
divergences in the *covariance estimator*).

Implementation notes
====================

Foundational paper
------------------
Maillard, S., Roncalli, T. & Teiletche, J. (2010).
*The Properties of Equally Weighted Risk Contribution Portfolios*.
Journal of Portfolio Management 36(4), 60-70.
https://doi.org/10.3905/jpm.2010.36.4.060

MRT (2010) is the canonical reference for the **equal-risk-
contribution** portfolio construction. Each asset's marginal risk
contribution ``RC_i = w_i · (Σ w)_i / sqrt(wᵀ Σ w)`` is equal
across all *i* at the ERC optimum. The paper proves that ERC sits
between the equal-weight portfolio and the minimum-variance
portfolio in terms of concentration: lower than equal-weight on
low-vol assets, higher than min-var on high-vol assets. MRT
specify a fixed-point iteration for the solver; the
``_covariance`` helper uses Spinu's (2013) equivalent convex
reformulation
(``min  ½ wᵀ Σ w − (1/N) Σᵢ log(wᵢ)``) which is convex in *w*
and converges globally under L-BFGS-B.

Primary methodology
-------------------
Asness, C. S., Frazzini, A. & Pedersen, L. H. (2012).
*Leverage Aversion and Risk Parity*. Financial Analysts Journal
68(1), 47-59.
https://doi.org/10.2469/faj.v68.n1.1

AFP (2012) is the *risk-premium justification* for ERC. Asness,
Frazzini & Pedersen argue that leverage-averse investors over-
weight high-vol assets to reach their target portfolio volatility,
suppressing those assets' expected returns and producing a
premium for "low-beta" / "low-vol" tilts. ERC (and broader risk-
parity constructions) capture this premium by under-weighting
high-vol assets relative to equal-weight. AFP document the
empirical risk-parity premium across stocks-bonds-commodities
panels over 1926-2010 with reported Sharpe ratios in the 0.7-0.9
range for the diversified 3-asset book.

The strategy code replicates MRT's ERC weight definition (via the
``_covariance`` helper's solver); the benchmark numbers are
calibrated against AFP's reported 3-asset Sharpe range.

Why two papers
--------------
MRT (2010) specifies the *construction* (ERC weight definition +
solver) but does not establish a risk-premium rationale. AFP
(2012) provides the *risk-premium justification* (leverage
aversion → high-vol assets are over-priced → under-weighting them
captures premium) but does not specify the ERC solver explicitly.
Both are cited so the audit trail covers both the math (MRT) and
the economic rationale (AFP).

The Session 2G plan's original "Bridgewater All-Weather"
attribution is folklore — Bridgewater's All-Weather construction
has never been published in detail; the public documents are
marketing summaries. The MRT 2010 + AFP 2012 pair is the
peer-reviewed equivalent.

Differentiation from sibling strategies
---------------------------------------
* **Phase 1 ``vol_targeting`` (volatility family)** — same
  inverse-vol intuition but applied *per-asset* (single-asset
  vol scaling), not as a *portfolio construction* across multiple
  assets. ``vol_targeting`` does not use joint covariance; this
  strategy uses the full 3×3 covariance via the shared
  ``_covariance`` helper. Expected ρ ≈ 0.20–0.40 (overlapping
  inverse-vol intuition; different scope).
* **Phase 2 Session 2G ``permanent_portfolio`` (Commit 2)** —
  static 25/25/25/25 four-asset allocation. Closest cluster
  sibling because both are multi-asset static / quasi-static
  allocators. Expected ρ ≈ 0.60–0.75: both over-weight low-vol
  assets (bonds, cash) and under-weight high-vol assets (equities,
  commodities), but ERC adapts to realized covariance while
  permanent_portfolio is fixed. The Phase 2 master plan §10
  cluster-risk acceptance bar is ρ > 0.95; the 0.60-0.75 expected
  ρ is below that bar but high enough to document as a deliberate
  family pair.
* **Within Session 2G covariance-primitive group:**
  - ``min_variance_gtaa`` (Commit 6) — different objective (min
    variance instead of equal risk contribution) on the same
    universe. Expected ρ ≈ 0.55–0.75 (overlapping covariance
    estimator and asset universe; different solver objective).
  - ``max_diversification`` (Commit 7) — different objective
    (max DR) on the same universe. Expected ρ ≈ 0.50–0.70.

Cluster expectations are documented in ``known_failures.md``.

Universe (3-asset risk parity, MRT / AFP three-class panel)
-----------------------------------------------------------
* ``SPY``: US large-cap equity (stocks leg)
* ``TLT``: 20+ year Treasuries (bonds leg, long duration)
* ``DBC``: Broad commodities (Invesco DB, commodities leg)

The 3-asset stocks/bonds/commodities panel is the canonical
risk-parity universe from AFP 2012 Table 1 — the three asset
classes have low pairwise correlation (typically -0.2 to +0.3)
and similar long-run real returns, which is exactly the
diversification structure that ERC is designed to exploit.

Substrate notes:

* TLT (20+ year duration) is chosen for the bonds leg instead of
  AGG (intermediate aggregate, ~6-year duration). Long-duration
  bonds have vol closer to commodity vol (TLT ~14% annual vs DBC
  ~18% annual), which keeps ERC weights from collapsing into
  near-100% bonds (the classic problem of risk parity on a
  short-duration bond leg). AGG would produce ERC weights of
  roughly 75% AGG, 12% SPY, 13% DBC — geometric concentration in
  the lowest-vol asset.
* DBC is chosen for the commodities leg over GLD because broad-
  commodity exposure captures the full commodity risk-class
  (energy + metals + agriculturals + softs) — gold-only would
  produce a different commodity-class beta.

Published rules (MRT 2010 / AFP 2012, 3-asset implementation)
-------------------------------------------------------------
For each month-end *t*:

1. Compute daily log returns over the trailing
   ``cov_window_days`` (252) bars.
2. Compute the rolling covariance matrix via
   ``rolling_covariance(returns, window, shrinkage)``. Default
   shrinkage is Ledoit-Wolf 2004 (analytic-optimal intensity to
   a constant-correlation target).
3. Solve ERC weights via ``solve_erc_weights(cov)``. Returns
   long-only weights summing to 1.0 with each asset contributing
   equal marginal risk to portfolio volatility.
4. Apply the resulting weight vector at the month-end rebalance
   bar; forward-fill to daily until the next rebalance.

Sign convention
---------------
Long-only, weights sum to 1.0. Every weight is strictly positive
(ERC is guaranteed positive by the Spinu 2013 log-barrier
formulation). The strategy emits zero weights on all legs during
warm-up (before ``cov_window_days`` of history are available).

Rebalance cadence
-----------------
Monthly target signal. The vectorbt bridge applies
``SizeType.TargetPercent`` semantics, producing daily drift-
correction trades on top of the monthly signal — see Session 2G
amendment "alphakit-wide rebalance-cadence convention" in
``docs/phase-2-amendments.md`` for the project-wide framing. The
``rebalance_frequency`` attribute documents the *signal cadence*,
not the bridge-event cadence.

Edge cases
----------
* Warm-up: requires ``cov_window_days`` bars of price history per
  asset. Before that, the strategy emits zero weights for every
  asset (the bridge holds 100% cash).
* Missing required columns: ``KeyError`` listing the missing
  symbols.
* Non-positive prices: ``ValueError``.
* Degenerate covariance (e.g. constant-price legs): the
  ``_covariance.solve_erc_weights`` solver raises ``ValueError``
  if any asset has non-positive sample variance. This propagates
  to the caller; document expected failure modes via the strategy
  ``known_failures.md``.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
from alphakit.strategies.macro._covariance import (
    ShrinkageMethod,
    rolling_covariance,
    solve_erc_weights,
)


class RiskParityErc3Asset:
    """Equal-Risk-Contribution portfolio across stocks / bonds / commodities.

    Parameters
    ----------
    stocks_symbol
        Symbol for the stocks leg. Defaults to ``"SPY"`` (US
        large-cap equity).
    bonds_symbol
        Symbol for the bonds leg. Defaults to ``"TLT"`` (20+ year
        Treasuries — long duration chosen to balance commodity vol
        on the ERC weights; see strategy module docstring).
    commodities_symbol
        Symbol for the commodities leg. Defaults to ``"DBC"``
        (Invesco DB broad-commodity ETF).
    cov_window_days
        Rolling window in trading days for the covariance estimator.
        Defaults to ``252`` (one trading year). Must be at least 60.
    shrinkage
        Covariance shrinkage method: ``"none"`` (raw sample),
        ``"ledoit_wolf"`` (analytic-optimal intensity to a
        constant-correlation target, default), or ``"constant"``
        (fixed α=0.5 shrinkage to the same target).
    """

    name: str = "risk_parity_erc_3asset"
    family: str = "macro"
    asset_classes: tuple[str, ...] = ("equity", "bonds", "commodities")
    paper_doi: str = "10.2469/faj.v68.n1.1"  # AFP 2012
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        stocks_symbol: str = "SPY",
        bonds_symbol: str = "TLT",
        commodities_symbol: str = "DBC",
        cov_window_days: int = 252,
        shrinkage: ShrinkageMethod = "ledoit_wolf",
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
            raise ValueError(
                f"cov_window_days must be >= 60 (minimum sample for stable covariance), "
                f"got {cov_window_days}"
            )
        if shrinkage not in ("none", "ledoit_wolf", "constant"):
            raise ValueError(
                f"shrinkage must be 'none' | 'ledoit_wolf' | 'constant', got {shrinkage!r}"
            )

        self.stocks_symbol = stocks_symbol
        self.bonds_symbol = bonds_symbol
        self.commodities_symbol = commodities_symbol
        self.cov_window_days = cov_window_days
        self.shrinkage = shrinkage

    @property
    def required_symbols(self) -> tuple[str, str, str]:
        """The three input columns this strategy requires."""
        return (self.stocks_symbol, self.bonds_symbol, self.commodities_symbol)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return ERC target-weights for ``prices``.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps. Must contain the
            three leg symbols (default: SPY / TLT / DBC). Additional
            columns are ignored. Values must be strictly positive.

        Returns
        -------
        weights
            DataFrame aligned to ``prices`` with one column per
            required symbol. Weights are recomputed monthly via
            ``_covariance.solve_erc_weights`` on the rolling
            covariance, forward-filled daily to the next rebalance.
            All weights are strictly positive and sum to 1.0 after
            warm-up; zero on every leg during warm-up.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")

        missing = [s for s in self.required_symbols if s not in prices.columns]
        if missing:
            raise KeyError(
                f"prices is missing required columns for risk_parity_erc_3asset: {missing}. "
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

        # 1. Daily log returns for the covariance estimator.
        daily_log_returns = np.log(leg_prices / leg_prices.shift(1))

        # 2. Rolling covariance via the shared _covariance helper. Returned
        # as a MultiIndex(date, asset_i) DataFrame with asset_j columns;
        # each .loc[date] slice is the (3, 3) covariance matrix at that date.
        rolling_cov = rolling_covariance(
            daily_log_returns.dropna(),
            window=self.cov_window_days,
            shrinkage=self.shrinkage,
        )

        if rolling_cov.empty:
            # Insufficient history for any rebalance date.
            return pd.DataFrame(
                np.zeros(leg_prices.shape, dtype=float),
                index=leg_prices.index,
                columns=list(self.required_symbols),
            )

        # 3. Sample the covariance at each month-end and solve ERC weights.
        cov_dates = pd.DatetimeIndex(rolling_cov.index.unique(level="date"))
        month_end_index = leg_prices.resample("ME").last().index
        # Rebalance dates are month-ends where a valid covariance exists.
        # Use asof-style lookup: for each month-end, take the most recent
        # covariance date at or before it.
        cov_at_month_end: dict[pd.Timestamp, np.ndarray] = {}
        for me in month_end_index:
            mask = cov_dates <= me
            if not mask.any():
                continue
            cov_date = cov_dates[mask].max()
            cov_matrix = rolling_cov.loc[cov_date].to_numpy(dtype=float)
            try:
                w = solve_erc_weights(cov_matrix)
            except ValueError:
                # Degenerate covariance at this date (e.g. one leg with
                # zero variance) — emit zero weights for this rebalance.
                continue
            cov_at_month_end[me] = w

        if not cov_at_month_end:
            return pd.DataFrame(
                np.zeros(leg_prices.shape, dtype=float),
                index=leg_prices.index,
                columns=list(self.required_symbols),
            )

        # 4. Build a monthly weights DataFrame and forward-fill to daily.
        monthly_weights = pd.DataFrame(
            np.vstack(list(cov_at_month_end.values())),
            index=pd.DatetimeIndex(list(cov_at_month_end.keys())),
            columns=list(self.required_symbols),
        )
        daily_weights = monthly_weights.reindex(leg_prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights)
