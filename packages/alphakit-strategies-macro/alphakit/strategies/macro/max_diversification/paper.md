# Paper — Maximum-Diversification Portfolio (CC 2008 / CFR 2013)

## Citations

**Initial inspiration:** Choueifaty, Y. & Coignard, Y. (2008).
**Toward Maximum Diversification.** *Journal of Portfolio
Management* 35(1), 40-51.
[https://doi.org/10.3905/JPM.2008.35.1.40](https://doi.org/10.3905/JPM.2008.35.1.40)

**Primary methodology:** Choueifaty, Y., Froidure, T. & Reynier, J.
(2013). **Properties of the Most Diversified Portfolio.**
*Journal of Investment Management* 11(3), 1-32. SSRN 1895459.
[https://doi.org/10.2139/ssrn.1895459](https://doi.org/10.2139/ssrn.1895459)

BibTeX entries are registered in `docs/papers/phase-2.bib` under
`choueifatyCoignard2008mdp` (foundational) and
`choueifatyFroidureReynier2013properties` (primary).

## Why two papers

CC 2008 provides the **construction** — defines the diversification
ratio

    DR(w) = (wᵀ σ) / sqrt(wᵀ Σ w)

(the ratio of the weighted average asset volatility to the
portfolio volatility) and proves that maximising DR produces the
unique long-only portfolio whose squared correlation with each
constituent asset is equal. The MDP is the "maximum diversification"
portfolio. CC 2008 Table 2 reports Sharpe ≈ 0.80 for the MDP on a
7-asset-class global multi-asset panel over 1959-2005.

CFR 2013 provides the **structural extensions** — three additional
properties used by this implementation:

1. **Capital allocation along the diversification frontier.** Any
   long-only portfolio can be decomposed as ``w = α · MDP +
   (1 - α) · cash``. The MDP is the diversification frontier's
   "tangent portfolio" — the optimal point for a
   diversification-targeting investor.
2. **Robustness to estimation error.** CFR document that MDP
   weights are less sensitive to estimation error in the
   covariance matrix than minimum-variance weights. This is a key
   advantage for the rolling-sample-covariance substrate the
   ``_covariance`` helper provides.
3. **Numerical stability under SLSQP.** The MDP problem
   (``max DR(w)`` s.t. sum-to-1 + box constraints) is a smooth
   constrained nonlinear program; SLSQP converges reliably on the
   3-asset problem in the helper's test suite.

Strategy code replicates CC's MDP weight definition (via the
``_covariance`` helper's ``solve_max_diversification_weights``);
benchmark numbers are calibrated against CC's reported 7-asset
Sharpe range, scaled down for the 3-asset substrate.

## Differentiation from sibling strategies

* **Phase 2 Session 2G `risk_parity_erc_3asset`** (Commit 5) —
  same universe, same covariance estimator. Different objective:
  ERC equalises *marginal risk contribution*; MDP maximises the
  *diversification ratio* (equal *correlation* with the portfolio).
  Expected ρ ≈ **0.50–0.70** — both exploit cross-asset
  correlations but MDP places more weight on assets with low
  correlation to the rest of the portfolio rather than on assets
  with low individual volatility. In our 3-asset panel where the
  asset classes have low pairwise correlation, MDP weights are
  closer to equal-weight than ERC or MV.
* **Phase 2 Session 2G `min_variance_gtaa`** (Commit 6) — same
  universe, same covariance estimator. Different objective: MV
  minimises portfolio variance; MDP maximises DR. Expected ρ ≈
  **0.55–0.75** — both use the long-only SLSQP solver but with
  different objectives. MV concentrates 60-80% in the lowest-vol
  asset (TLT); MDP spreads across the asset classes with the
  lowest-correlation pairs (typically 25-40% each in our 3-asset
  universe).
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  static 25/25/25/25 four-asset allocation. Expected ρ ≈
  0.40–0.60 — MDP's diversification-maximising weights are
  *closest* to 25/25/25/25 of the three covariance-primitive
  strategies because both philosophies target balanced cross-asset
  exposure.
* **Phase 1 `vol_targeting`** (volatility family) — per-asset
  inverse-vol scaling. Expected ρ ≈ 0.20–0.40.

## Architectural note: shared `_covariance` helper

This is the **third strategy** in Session 2G to consume the
`alphakit.strategies.macro._covariance` helper. Commit 1.5 ships
the helper; Commit 5 establishes the integration pattern; Commits
5-7 form an architecturally coupled trio with the helper at the
centre. This strategy imports:

* `rolling_covariance(returns, window, shrinkage)` — identical
  to Commits 5 and 6.
* `solve_max_diversification_weights(cov, long_only, max_weight)`
  — SciPy SLSQP minimising the negative diversification ratio.

The covariance estimator is **identical** across the three
covariance-primitive strategies; only the solver objective differs.
This is the architectural guarantee that the trio's pairwise
cluster ρ values reflect *solver-objective differences* (ERC vs MV
vs MDP), not arbitrary estimator divergences.

The helper's analytic-anchor coverage for MDP includes the
equal-correlation-equal-vol → equal-weight test (4 assets with
identical vol and pairwise correlation produce equal weights),
verified to atol=1e-5 in `tests/test_covariance.py`.

## Published rules (CC 2008 / CFR 2013, 3-asset implementation)

For each month-end *t*:

1. Compute daily log returns over the trailing `cov_window_days`
   (default 252) bars.
2. Compute the rolling covariance matrix `Σ_t` via
   `_covariance.rolling_covariance(returns, window, shrinkage)`.
3. Solve the long-only MDP weights via
   `_covariance.solve_max_diversification_weights(Σ_t,
   long_only=True, max_weight=max_weight)`:

       max_w  DR(w) = (wᵀ σ) / sqrt(wᵀ Σ w)
       s.t.   sum(w) = 1
              0 ≤ w_i ≤ max_weight

   The solver implements this as the equivalent minimisation
   ``min_w  −DR(w)`` via SciPy SLSQP.

4. Apply weights at the month-end rebalance bar; forward-fill to
   daily until the next rebalance.

| Parameter | CC 2008 / CFR 2013 | AlphaKit default | Notes |
|---|---|---|---|
| Objective | max DR(w) | Same | identical |
| Long-only constraint | Yes (CC §III) | Yes | identical |
| Sum-to-1 constraint | Yes | Yes | identical |
| Per-asset weight cap | varies | 1.0 (no cap) | configurable via `max_weight` |
| Solver | Quadratic / SQP variants | SciPy SLSQP | numerically equivalent |
| Covariance window | Various (24-60 months) | 252 days | within paper's range |
| Shrinkage | None / sample cov | Ledoit-Wolf 2004 | improves stability |
| Universe | Multi-asset (CC: 7 classes; CFR: ~16) | SPY / TLT / DBC | 3-asset substrate |
| Rebalance | Monthly | Monthly | identical |

## Data Fidelity

* **Substrate:** daily closing prices from yfinance for 3 ETFs.
  Universe matches `risk_parity_erc_3asset` and `min_variance_gtaa`.
* **No transaction costs in synthetic fixture.** The vectorbt
  bridge applies a configurable flat `commission_bps` per
  rebalance leg.
* **Rebalance cadence:** monthly target signal, daily bridge-side
  drift correction (AlphaKit-wide convention).
* **CFR 2013 estimation-robustness property.** MDP weights are
  documented to be less sensitive to covariance-estimation error
  than MV weights — empirically the monthly MDP re-solve
  produces smaller weight shifts (5-15 percentage points) than
  the monthly MV re-solve (10-30 pct points). This is reflected
  in the lower turnover number in `benchmark_results.json`.

## Expected Sharpe range

`0.5 – 0.8 OOS` (CC 2008 reports Sharpe ≈ 0.80 for the MDP on a
7-asset-class global panel; the lower bound 0.5 accounts for the
narrower 3-asset substrate and the rolling-sample-covariance
estimator). CFR 2013 reports comparable Sharpe ratios on similar
samples.

## Implementation deviations from CC 2008 / CFR 2013

1. **SciPy SLSQP** solver instead of dedicated SQP variants. The
   MDP problem is a smooth constrained nonlinear program; SLSQP
   converges reliably on the 3-asset problem.
2. **Ledoit-Wolf 2004 shrinkage** on the covariance estimator.
   CFR 2013's robustness-to-estimation-error property partially
   addresses the underlying motivation for shrinkage; we apply
   both for compound stability.
3. **3-asset multi-class universe** instead of CC's 7-asset or
   CFR's 16-asset panels. The MDP methodology applies to any
   covariance matrix; the smaller universe is substrate-driven.
4. **No bid-ask, financing, or short-borrow model.** Long-only,
   three-leg allocation.

## Known replications and follow-ups

* **TOBAM** (Choueifaty's investment firm) publishes ongoing
  research on MDP applications across asset classes. The
  technique is in production use at multi-billion-dollar AUM.
* **Roncalli, T. (2013)** — *Introduction to Risk Parity and
  Budgeting*, Chapman & Hall (ISBN 9781482207156). Treats MDP
  alongside ERC and MV — the same allocator trio as Session 2G's
  covariance group.
* **Chaves, D., Hsu, J., Li, F. & Shakernia, O. (2011)** —
  *Risk Parity Portfolio vs. Other Asset Allocation Heuristic
  Portfolios*, J of Investing. Empirical comparison includes MDP.
