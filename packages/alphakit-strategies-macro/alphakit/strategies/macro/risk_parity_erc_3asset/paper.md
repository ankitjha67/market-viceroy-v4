# Paper — Equal-Risk-Contribution Portfolio (MRT 2010 / AFP 2012)

## Citations

**Initial inspiration:** Maillard, S., Roncalli, T. & Teiletche, J.
(2010). **The Properties of Equally Weighted Risk Contribution
Portfolios.** *Journal of Portfolio Management* 36(4), 60-70.
[https://doi.org/10.3905/jpm.2010.36.4.060](https://doi.org/10.3905/jpm.2010.36.4.060)

**Primary methodology:** Asness, C. S., Frazzini, A. & Pedersen,
L. H. (2012). **Leverage Aversion and Risk Parity.** *Financial
Analysts Journal* 68(1), 47-59.
[https://doi.org/10.2469/faj.v68.n1.1](https://doi.org/10.2469/faj.v68.n1.1)

BibTeX entries are registered in `docs/papers/phase-2.bib` under
`maillardRoncalliTeiletche2010erc` (foundational) and
`asnessFrazziniPedersen2012leverage` (primary).

## Why two papers

MRT 2010 is the canonical reference for the **equal-risk-
contribution** construction. The paper defines the ERC weights and
proves three structural properties:

1. ERC sits between the equal-weight and minimum-variance
   portfolios in terms of asset concentration. For diagonal
   covariance (uncorrelated assets), ERC reduces to inverse-
   volatility weights.
2. ERC is the unique long-only portfolio whose marginal risk
   contributions ``w_i · (Σw)_i / sqrt(wᵀΣw)`` are equal across
   all assets.
3. ERC is solvable via fixed-point iteration. (The
   ``_covariance`` helper uses Spinu's 2013 equivalent convex
   reformulation
   ``min  ½ wᵀΣw − (1/N) Σᵢ log(wᵢ)`` which converges globally
   under L-BFGS-B with positive box bounds.)

AFP 2012 provides the **risk-premium justification**. Asness,
Frazzini & Pedersen argue:

* Investors are leverage-averse: they cannot freely lever a
  low-risk portfolio up to their target portfolio volatility.
* Leverage-averse investors therefore over-weight high-vol assets
  to reach their target vol, *bidding up the prices* of those
  high-vol assets.
* High-vol assets earn lower expected returns per unit of risk
  (the "low-beta" / "low-vol" anomaly).
* Risk-parity / ERC portfolios *under-weight* high-vol assets
  relative to market-cap weighting and capture this premium.

AFP document the empirical risk-parity premium across stocks /
bonds / commodities panels over 1926-2010 with Sharpe ratios in
the 0.7-0.9 range for the diversified 3-asset book.

Strategy code replicates MRT's ERC weight definition (via the
``_covariance`` helper); benchmark numbers are calibrated against
AFP's reported 3-asset Sharpe range.

The Session 2G plan's original "Bridgewater All-Weather"
attribution is folklore — Bridgewater's All-Weather construction
has never been published in detail. The MRT 2010 + AFP 2012 pair
is the peer-reviewed equivalent; the reframe is documented in
``docs/phase-2-amendments.md`` "Session 2G: reframe
risk_parity_3asset → risk_parity_erc_3asset".

## Differentiation from sibling strategies

* **Phase 1 `vol_targeting`** (volatility family) — same inverse-
  vol intuition but applied *per-asset* (single-asset vol scaling),
  not as a *portfolio construction* across multiple assets. ERC
  uses the full joint covariance via the shared `_covariance`
  helper. Expected ρ ≈ 0.20–0.40.
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  closest cluster sibling because both are multi-asset
  static / quasi-static allocators. Both over-weight low-vol
  assets (bonds, cash) and under-weight high-vol assets (equities,
  commodities). The difference is that ERC adapts to *realized*
  covariance while permanent_portfolio is fixed 25/25/25/25.
  Expected ρ ≈ **0.60–0.75** — well below the Phase 2 master plan
  §10 deduplication-review bar (ρ > 0.95) but documented as a
  deliberate family pair.
* **Within Session 2G covariance-primitive group (same `_covariance`
  helper):**
  - `min_variance_gtaa` (Commit 6) — different objective (minimum
    variance instead of equal risk contribution). Expected ρ ≈
    0.55–0.75 (overlapping covariance estimator; different solver
    objective). The covariance estimator is *identical*; only the
    weight-construction differs.
  - `max_diversification` (Commit 7) — different objective (max
    diversification ratio). Expected ρ ≈ 0.50–0.70.
* **Phase 1 `dual_momentum_gem`** (trend family) — discrete
  100%-allocation momentum rotation. Different shape entirely.
  Expected ρ ≈ 0.20–0.40.

## Architectural note: shared `_covariance` helper

This is the **first strategy** in Session 2G to consume the
``alphakit.strategies.macro._covariance`` helper module that
shipped in Commit 1.5. The helper provides:

* ``rolling_covariance(returns, window, shrinkage)`` — rolling
  covariance with optional Ledoit-Wolf 2004 shrinkage.
* ``solve_erc_weights(cov)`` — convex Spinu 2013 reformulation
  with L-BFGS-B + log-barrier.

The same helper is consumed by Commit 6 (`min_variance_gtaa`,
via ``solve_min_variance_weights``) and Commit 7
(`max_diversification`, via ``solve_max_diversification_weights``).
Sharing the helper across the three solvers preserves cluster-
prediction integrity: their pairwise ρ values reflect
methodological differences in the *solver objective*, not
arbitrary divergences in the *covariance estimator*.

The helper is exhaustively tested (41 tests in
``packages/alphakit-strategies-macro/tests/test_covariance.py``
including the analytic-known-result anchors: ERC inverse-vol on
uncorrelated assets, 2-asset Markowitz min-var closed form, equal-
correlation equal-vol → equal-weight MDP). See Commit 1.5 and
``docs/phase-2-amendments.md`` "Session 2G: covariance-primitive
shared helper module" for the helper's gate-3 review trail.

## Published rules (MRT 2010 / AFP 2012, 3-asset implementation)

For each month-end *t*:

1. Compute daily log returns over the trailing ``cov_window_days``
   (default 252) bars.
2. Compute the rolling covariance matrix ``Σ_t`` via
   ``_covariance.rolling_covariance(returns, window, shrinkage)``.
   Default shrinkage is Ledoit-Wolf 2004 with the analytic-optimal
   intensity to a constant-correlation target.
3. Solve ERC weights via ``_covariance.solve_erc_weights(Σ_t)``.
   The solver returns long-only weights summing to 1.0 with each
   asset contributing equal marginal risk to portfolio volatility.
4. Apply weights at the month-end rebalance bar; forward-fill to
   daily until the next rebalance.

| Parameter | MRT 2010 / AFP 2012 | AlphaKit default | Notes |
|---|---|---|---|
| ERC weight definition | Equal RC, long-only | Same | identical |
| Solver | Fixed-point iteration | Spinu 2013 convex reformulation + L-BFGS-B | equivalent at the optimum |
| Covariance window | Various (24-60 months) | 252 days (~12 months) | within paper's range |
| Shrinkage | None / sample cov | Ledoit-Wolf 2004 | improves numerical stability on small samples |
| Universe | Stocks / bonds / commodities | SPY / TLT / DBC | ETF substrate; 3-asset canonical |
| Rebalance | Monthly | Monthly | identical |

## Data Fidelity

* **Substrate:** daily closing prices from yfinance for 3 ETFs:
  SPY (1993), TLT (2002), DBC (2006). The continuous panel begins
  2006-02 once DBC is live.
* **Bond-leg duration choice (TLT not AGG).** TLT (20+ year
  Treasuries, ~17-year duration) is chosen instead of AGG
  (aggregate, ~6-year duration) so the bond-leg vol is closer to
  commodity vol. With AGG, ERC weights collapse into ~75% AGG /
  12% SPY / 13% DBC — geometric concentration in the lowest-vol
  asset, which defeats the purpose of cross-asset diversification.
  With TLT, weights are roughly 30-45% TLT / 25-35% SPY / 25-35%
  DBC, which preserves cross-asset balance.
* **No transaction costs in synthetic fixture.** The vectorbt
  bridge applies a configurable flat ``commission_bps`` per
  rebalance leg. The in-repo benchmark in
  ``benchmark_results.json`` reports headline metrics at
  ``commission_bps = 5.0``.
* **Rebalance cadence:** monthly target signal, daily bridge-side
  drift correction (AlphaKit-wide convention; see Session 2G
  amendment "alphakit-wide rebalance-cadence convention").

## Expected Sharpe range

`0.6 – 0.9 OOS` (AFP 2012 reports Sharpe ≈ 0.75 for the
diversified 3-asset risk-parity book over 1926-2010; MRT 2010
reports comparable Sharpe on similar samples). The lower bound of
0.6 accounts for the AlphaKit substrate (ETF-based vs total-
return indices) and the rolling 252-day covariance estimator (vs
AFP's longer-window estimates). The upper bound of 0.9 reflects
AFP's reported maximum across in-sample and out-of-sample windows.

## Implementation deviations from MRT 2010 / AFP 2012

1. **Spinu 2013 convex reformulation** of the ERC problem instead
   of MRT's fixed-point iteration. The two formulations have the
   same optimum (rigorously proven in Spinu 2013); the convex
   reformulation is more numerically stable under L-BFGS-B.
2. **Ledoit-Wolf 2004 shrinkage** on the covariance estimator
   instead of plain sample covariance. The analytic-optimal
   intensity α ∈ [0, 1] reduces estimation error on small samples.
   For the default 252-day window with 3 assets (T=252, N=3), the
   typical α is in the 0.1-0.3 range — small shrinkage, but
   non-zero. Phase 3 users wanting the pure-sample variant can
   switch via the ``shrinkage="none"`` constructor parameter.
3. **No bid-ask, financing, or short-borrow model.** Long-only,
   three-leg allocation — no shorting, no leverage. The bridge
   applies a flat ``commission_bps`` per rebalance leg.

None of these change the ERC weight definition or the structural
properties of the resulting portfolio.

## Known replications and follow-ups

* **Bridgewater (2010s)** — All-Weather fund marketing documents.
  Folklore-grade descriptions of a multi-regime risk-parity
  construction. *No peer-reviewed reference; not cited as a
  primary source.* The 4-regime framing in Browne 1987 and the
  ERC math in MRT 2010 together cover the analytical content of
  the Bridgewater construction without the marketing layer.
* **Roncalli, T. (2013)** — *Introduction to Risk Parity and
  Budgeting*, Chapman & Hall (ISBN 9781482207156). Book-length
  treatment of ERC and broader risk-budgeting frameworks; the
  ``_covariance`` helper's Spinu 2013 reformulation is consistent
  with Roncalli's framing.
* **Chaves, D., Hsu, J., Li, F. & Shakernia, O. (2011)** —
  *Risk Parity Portfolio vs. Other Asset Allocation Heuristic
  Portfolios*, J of Investing. Empirical comparison of ERC,
  equal-weight, minimum-variance, and 60/40 on multi-asset
  panels — the standard reference for cross-allocator comparison.
