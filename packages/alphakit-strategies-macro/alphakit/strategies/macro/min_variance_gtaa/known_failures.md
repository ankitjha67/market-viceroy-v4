# Known failure modes — min_variance_gtaa

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

CST (2006) / HB (1991) long-only Minimum-Variance portfolio on
a 3-asset stocks / bonds / commodities panel (SPY / TLT / DBC).
Second consumer of the shared `_covariance` helper module —
covariance-estimation failure modes are identical to those in
`risk_parity_erc_3asset` and are cross-referenced rather than
duplicated.

## 1. Real-rate spikes (2022)

When real interest rates rise sharply, the MV solution's heavy
TLT concentration (typically 60-80% on long-duration Treasuries
because TLT has the lowest realized vol in most periods) becomes
a structural liability. The 2022 Fed-tightening cycle: TLT lost
31% peak-to-trough; MV portfolio took ~25% drawdown (worse than
risk_parity_erc_3asset's ~22% because MV concentrates more
heavily in TLT).

Expected behaviour in real-rate-spike regimes:

* Sharpe of −0.5 to −0.8 over the regime window.
* Max drawdown of 22–32% — the worst regime for any allocator
  that over-weights long-duration bonds.

Mitigation:
* Use `max_weight=0.5` or lower to cap the bond concentration.
* Pair with a duration-aware overlay (Phase 1 `real_yield_momentum`
  or Session 2G `growth_inflation_regime_rotation`).

## 2. Covariance-estimation failure modes (shared with risk_parity_erc_3asset)

This strategy inherits all the covariance-estimation failure
modes documented in `risk_parity_erc_3asset/known_failures.md`
item 2:

* Constant-price legs trigger ValueError → zero-weight emission
  for the affected rebalance.
* Rolling-window edge: 252-day warm-up emits zero weights.
* Ledoit-Wolf shrinkage intensity α can spike to 0.5-0.7 in
  high-correlation regimes (2020 March); the solver still
  converges but weights are less responsive to real correlation
  structure.

Cross-reference rather than duplicate. The covariance estimator
is identical between the three Session 2G covariance-primitive
strategies; failure modes that originate in the helper propagate
identically.

## 3. Long-only constraint binding (load-bearing MV-specific failure)

The defining structural property of *long-only* MV is that the
constraint **binds** when the unconstrained MV solution would
short a high-vol asset. SLSQP clips that asset's weight to
exactly zero and rebalances the remaining weight across the
non-binding assets.

When binding occurs:

* The MV solution loses a degree of freedom — instead of solving
  for 3 weights, it solves for 2 weights with one fixed at zero.
* Portfolio variance is higher than the unconstrained MV
  variance (the long-only solution is *not* on the global
  efficient frontier).
* Realised behaviour: the strategy effectively reduces to a
  2-asset min-variance problem on the remaining legs.

Historical examples:

* **2020 March COVID:** SPY's 6-month realized vol jumped to
  45%+, with strong positive correlation to DBC (commodities
  also crashed). The unconstrained MV solution would short SPY;
  the long-only solution clipped SPY to zero and held a
  TLT/DBC-only portfolio. SPY rebounded sharply in April, but
  the strategy was already 100% out of equity.
* **Crisis-tail risk** generally: long-only MV systematically
  *misses* the rebound after equity-vol-spike crises because
  the constraint binds at zero exactly when the equity asset's
  forward expected return is highest.

This is the *cost of the long-only constraint*. Phase 3 users
who can tolerate shorts should explore an unconstrained MV
variant (the `_covariance` helper's `solve_min_variance_weights`
accepts `long_only=False`).

## 4. Lowest-vol-asset concentration

A structural feature of long-only MV: the solution typically
concentrates 60-80% of the portfolio in the lowest-vol asset.
For SPY/TLT/DBC, TLT (long-duration Treasuries) has the lowest
realized vol in most periods (excluding 2022); MV concentrates
heavily in TLT.

Concentration risk:

* When TLT realised vol changes sharply (regime transition),
  MV re-solves and shifts weight aggressively — month-over-month
  weight changes of 10-30 percentage points are common.
* When TLT *itself* has a bad month, the portfolio takes the
  full hit. 2022 illustrates this acutely — TLT was the lowest-
  vol asset until early 2022, so MV held 75-85% TLT entering the
  Fed-tightening cycle, and the portfolio took the full duration
  shock.

Mitigation: set `max_weight=0.5` or `max_weight=0.6` via the
constructor to cap the per-asset weight. This forces diversification
at the cost of higher portfolio variance.

## 5. Rebalance-cadence: monthly signal, daily bridge-side drift correction

Inherits the AlphaKit-wide convention: monthly target signal
+ bridge-side daily drift correction by vectorbt's
`SizeType.TargetPercent`. For min_variance_gtaa specifically:

* ~63 daily drift-correction events per asset per year.
* Plus monthly MV re-solve events that can shift weights by
  10-30 percentage points (more aggressive than ERC's 5-15%
  shifts).
* On regime-transition months (e.g. equity vol spike), the
  re-solve event can produce a 50+ percentage point weight
  swap — a much larger rebalance event than the other Session
  2G covariance group strategies.

See `docs/phase-2-amendments.md` "Session 2G: alphakit-wide
rebalance-cadence convention" for the full project-wide audit
trail.

## 6. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **Phase 2 Session 2G `risk_parity_erc_3asset`** (Commit 5) —
  closest cluster sibling. Same universe, same covariance
  estimator, different solver objective. Expected ρ ≈
  **0.55–0.75**. Both over-weight low-vol assets, but MV is
  more aggressive about it (60-80% TLT concentration vs ERC's
  30-45%). The two strategies diverge most in regime-transition
  periods when MV's lowest-vol-asset bias becomes a liability.
* **Phase 2 Session 2G `max_diversification`** (Commit 7) —
  third covariance-primitive sibling. Expected ρ ≈ 0.55–0.75.
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  static 25/25/25/25 allocator. Expected ρ ≈ 0.50–0.70 (MV's
  TLT-heavy concentration is more aggressive than 25/25/25/25's
  even split).
* **Phase 1 `vol_targeting`** (volatility family) — per-asset
  inverse-vol scaling. Expected ρ ≈ 0.20–0.40.

The Session 2G covariance-primitive trio (ERC / MV / MDP)
forms an architecturally coupled cluster — pairwise ρ values
in the 0.55-0.75 range reflect methodology differences (solver
objective) under a shared covariance estimator. This is
deliberate; the Phase 2 master plan §10 dedup-review bar is
ρ > 0.95, well above any of the trio's pairwise correlations.

## 7. Solver convergence (theoretical + practical)

SciPy SLSQP for quadratic objective + linear equality + box
constraints is a well-studied numerical method with reliable
convergence on small problems (N=3). The `_covariance` helper's
`solve_min_variance_weights` includes a `result.success` check
and raises `ValueError` on convergence failure — propagated by
this strategy as a zero-weight emission for the affected
rebalance.

Empirically, SLSQP has not failed on any 3-asset MV problem in
the helper's test suite (39 tests covering edge cases including
binding constraint, long-short comparison, n=10 random PSD
covariance). Production convergence failures on the 3-asset
universe would be unprecedented.

## Regime performance (reference, from CST 2006 Table 4 + HB 1991 + practitioner data)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-GFC bull (2003-07) | 2003-04 – 2007-09 | ~0.7 | −5% |
| GFC crisis (2007-09) | 2007-10 – 2009-03 | ~0.5 | −18% |
| Post-GFC reflation (2010-14) | 2010-01 – 2014-12 | ~0.8 | −8% |
| Range-bound (2015-18) | 2015-01 – 2018-12 | ~0.6 | −10% |
| COVID + recovery (2020-21) | 2020-01 – 2021-12 | ~0.5 | −18% (constraint-binding miss on recovery) |
| Real-rate spike (2022) | 2022-01 – 2022-12 | ~−0.7 | −25% (TLT concentration) |

(Reference ranges from CST 2006 Table 4, HB 1991, and
practitioner sources; the in-repo benchmark is the authoritative
source for this implementation — see
[`benchmark_results.json`](benchmark_results.json).)
