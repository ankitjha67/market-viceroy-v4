# Paper — Long-Only Minimum-Variance Portfolio (CST 2006 / HB 1991)

## Citations

**Initial inspiration:** Clarke, R., de Silva, H. & Thorley, S.
(2006). **Minimum-Variance Portfolios in the U.S. Equity Market.**
*Journal of Portfolio Management* 33(1), 10-24.
[https://doi.org/10.3905/jpm.2006.661366](https://doi.org/10.3905/jpm.2006.661366)

**Primary methodology:** Haugen, R. A. & Baker, N. L. (1991).
**The Efficient Market Inefficiency of Capitalization-Weighted
Stock Portfolios.** *Journal of Portfolio Management* 17(3), 35-40.
[https://doi.org/10.3905/jpm.1991.409335](https://doi.org/10.3905/jpm.1991.409335)

BibTeX entries are registered in `docs/papers/phase-2.bib` under
`clarkeDeSilvaThorley2006mv` (foundational) and
`haugenBaker1991efficient` (primary).

## Why two papers

CST 2006 provides the **construction** — the long-only minimum-
variance optimisation framework with rigorous documentation of
the resulting portfolio's Sharpe / volatility properties. The
paper proves that the long-only MV portfolio has lower realised
variance than the equal-weight portfolio out-of-sample, and the
constrained-optimisation framework it develops (sum-to-1 equality
+ per-asset box constraints) is exactly what the `_covariance`
helper's `solve_min_variance_weights` implements via SciPy SLSQP.

The CST §III 1/N-vs-MV comparison establishes that any investor
with a target portfolio volatility lower than equal-weight's
realised vol should prefer MV — a foundational result for the
multi-asset MV literature.

HB 1991 provides the **empirical premium** — the low-volatility
anomaly that makes minimum-variance portfolios attractive on a
risk-adjusted basis. Haugen & Baker document that capitalization-
weighted equity indices are *mean-variance inefficient*: a low-
vol-tilted portfolio earns the same expected return at lower
realised variance. This paper predates the modern "low-vol
anomaly" / "betting against beta" literature (Frazzini & Pedersen
2014) by two decades and provides the historical empirical
foundation that CST 2006 formalises.

Strategy code replicates CST's long-only MV optimisation (via the
`_covariance` helper's solver); benchmark numbers are calibrated
against HB / CST's reported Sharpe and volatility properties.

## Differentiation from sibling strategies

* **Phase 2 Session 2G `risk_parity_erc_3asset`** (Commit 5) —
  closest cluster sibling in the covariance-primitive group.
  Same universe, same covariance estimator (`_covariance`
  helper). Difference: ERC objective (equal marginal risk
  contribution) vs MV objective (minimum portfolio variance).
  Expected ρ ≈ **0.55–0.75** — both over-weight low-vol assets,
  but MV is more aggressive about it. The MV solution typically
  concentrates 60-80% in the lowest-vol asset (TLT in our
  universe) while ERC bounds the concentration via the equal-
  contribution constraint. Documented as a deliberate Session 2G
  family pair below the Phase 2 master plan §10 dedup-review
  bar (ρ > 0.95).
* **Phase 2 Session 2G `max_diversification`** (Commit 7) —
  third member of the covariance-primitive group. Same universe,
  same helper. Expected ρ ≈ 0.55–0.75 — MV minimises portfolio
  variance, MDP maximises the diversification ratio; both exploit
  the same covariance estimator but with different objectives.
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  static 25/25/25/25 four-asset allocation. Expected ρ ≈
  0.50–0.70 — multi-asset static-ish allocator; MV is more
  concentrated than 25/25/25/25 because of the heavy bond tilt.
* **Phase 1 `vol_targeting`** (volatility family) — per-asset
  inverse-vol scaling, not joint covariance. Expected ρ ≈
  0.20–0.40.

## Architectural note: shared `_covariance` helper

This is the **second strategy** in Session 2G to consume the
`alphakit.strategies.macro._covariance` helper (Commit 1.5 ships
the helper, Commit 5 establishes the integration pattern). This
strategy imports:

* `rolling_covariance(returns, window, shrinkage)` — rolling
  covariance with Ledoit-Wolf 2004 shrinkage (identical to
  Commit 5's usage).
* `solve_min_variance_weights(cov, long_only, max_weight)` —
  SciPy SLSQP with sum-to-1 equality + per-asset box constraints.

The covariance estimator is **identical** to `risk_parity_erc_3asset`
— only the solver objective differs. This is the core architectural
guarantee of the covariance-primitive group: their pairwise cluster
ρ values reflect *solver-objective differences* (ERC vs MV vs MDP),
not arbitrary covariance-estimator divergences.

The helper's analytic-anchor coverage includes 2-asset Markowitz
closed-form tests for `solve_min_variance_weights` (uncorrelated
and correlated cases) and a long-only-constraint-binding test
that verifies the SLSQP solver clips a negative-unconstrained
weight to exactly zero — see `tests/test_covariance.py` in the
package root.

## Published rules (CST 2006 / HB 1991, 3-asset implementation)

For each month-end *t*:

1. Compute daily log returns over the trailing `cov_window_days`
   (default 252) bars.
2. Compute the rolling covariance matrix `Σ_t` via
   `_covariance.rolling_covariance(returns, window, shrinkage)`.
   Default shrinkage is Ledoit-Wolf 2004.
3. Solve the long-only minimum-variance weights via
   `_covariance.solve_min_variance_weights(Σ_t, long_only=True,
   max_weight=max_weight)`:

       min_w  wᵀ Σ w
       s.t.   sum(w) = 1
              0 ≤ w_i ≤ max_weight

4. Apply weights at the month-end rebalance bar; forward-fill to
   daily until the next rebalance.

| Parameter | CST 2006 / HB 1991 | AlphaKit default | Notes |
|---|---|---|---|
| Objective | min wᵀΣw | Same | identical |
| Long-only constraint | Yes (CST §II) | Yes | identical |
| Sum-to-1 constraint | Yes | Yes | identical |
| Per-asset weight cap | varies | 1.0 (no cap) | configurable via `max_weight` |
| Solver | Quadratic programming | SciPy SLSQP | numerically equivalent |
| Covariance window | Various (24-60 months) | 252 days | within paper's range |
| Shrinkage | None / sample cov | Ledoit-Wolf 2004 | improves stability |
| Universe | US equity (CST) / global eq (HB) | SPY / TLT / DBC | 3-asset multi-class |
| Rebalance | Monthly | Monthly | identical |

## Data Fidelity

* **Substrate:** daily closing prices from yfinance for 3 ETFs.
  Universe is identical to `risk_parity_erc_3asset` — see that
  strategy's `paper.md` for the substrate notes (TLT-vs-AGG
  rationale, DBC-vs-GLD rationale).
* **Long-only constraint binds in some regimes.** When the
  unconstrained MV solution would short a high-vol asset (e.g.
  during equity-vol-spike crises), the SLSQP solver clips that
  asset's weight to exactly zero. Documented in
  `known_failures.md` item 3.
* **No transaction costs in synthetic fixture.** The vectorbt
  bridge applies a configurable flat `commission_bps` per
  rebalance leg.
* **Rebalance cadence:** monthly target signal, daily bridge-side
  drift correction (AlphaKit-wide convention).

## Expected Sharpe range

`0.5 – 0.8 OOS` (CST 2006 reports Sharpe ≈ 0.7 for the long-only
MV portfolio on US equity 1968-2005; HB 1991 reports comparable
risk-adjusted returns on the broader US universe). The lower
bound of 0.5 accounts for the 3-asset substrate (vs CST's
broader US equity universe) and the daily-bar implementation.
The upper bound of 0.8 reflects the documented range across
in-sample and out-of-sample windows in the original literature.

## Implementation deviations from CST 2006 / HB 1991

1. **SciPy SLSQP** solver instead of a dedicated QP solver. SLSQP
   handles quadratic objectives + linear constraints correctly;
   the long-only-binding behaviour is verified analytically in
   the `_covariance` helper's test suite.
2. **Ledoit-Wolf 2004 shrinkage** on the covariance estimator
   instead of plain sample covariance — see
   `risk_parity_erc_3asset` `paper.md` for the rationale; same
   choice across the Session 2G covariance group.
3. **3-asset multi-class universe** instead of CST's single-
   asset-class US equity universe. The CST methodology applies
   to any covariance matrix; the multi-asset adaptation is
   substrate-driven (yfinance ETFs at daily frequency).
4. **No bid-ask, financing, or short-borrow model.** Long-only,
   three-leg allocation; no shorting, no leverage.

## Known replications and follow-ups

* **Frazzini, A. & Pedersen, L. H. (2014)** — *Betting Against
  Beta*, JFE. Modern formalisation of the low-vol anomaly that
  HB 1991 originally documented. Provides the leverage-aversion
  microeconomic explanation that AFP 2012 (cited by
  `risk_parity_erc_3asset`) extends to multi-asset risk parity.
* **Roncalli, T. (2013)** — *Introduction to Risk Parity and
  Budgeting*, Chapman & Hall (ISBN 9781482207156). Book-length
  treatment that covers long-only MV alongside ERC and MDP —
  the same allocator trio as Session 2G's covariance group.
* **Chaves, D., Hsu, J., Li, F. & Shakernia, O. (2011)** —
  *Risk Parity Portfolio vs. Other Asset Allocation Heuristic
  Portfolios*, J of Investing. Empirical comparison of MV, ERC,
  equal-weight, and 60/40 on multi-asset panels.
