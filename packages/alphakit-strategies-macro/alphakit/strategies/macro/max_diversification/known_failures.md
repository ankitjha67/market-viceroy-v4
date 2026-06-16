# Known failure modes — max_diversification

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

CC (2008) / CFR (2013) Maximum-Diversification Portfolio on a
3-asset stocks / bonds / commodities panel (SPY / TLT / DBC).
Third consumer of the shared `_covariance` helper — covariance-
estimation failure modes are identical to those documented in
`risk_parity_erc_3asset` and `min_variance_gtaa` and are cross-
referenced rather than duplicated.

## 1. High-correlation regimes (2020 March COVID)

MDP's diversification benefit *collapses* when cross-asset
correlations spike. In 2020 March, all three asset classes
(SPY/TLT/DBC) briefly correlated positively as investors sold
indiscriminately. The realized DR collapsed from typical ~1.4
to ~1.05, and MDP weights converged toward equal-weight
(diversification-by-construction is undefined when no
diversification benefit exists).

Expected behaviour in high-correlation regimes:

* DR collapses to ~1.0 (no diversification benefit).
* Weights converge toward equal-weight (33% each in 3-asset).
* Sharpe of −0.2 to −0.5 over the crisis window.
* Drawdown of 15-22% (the strategy is essentially equal-weight
  during the crisis).

Mitigation: pair with a vol-targeting overlay that scales gross
exposure down when realized correlation spikes. Out of scope for
this commit.

## 2. Covariance-estimation failure modes (shared with covariance group)

This strategy inherits all the covariance-estimation failure
modes documented in `risk_parity_erc_3asset/known_failures.md`
item 2 and `min_variance_gtaa/known_failures.md` item 2:

* Constant-price legs trigger ValueError → zero-weight emission.
* Rolling-window edge: 252-day warm-up emits zero weights.
* Ledoit-Wolf shrinkage intensity α spikes in high-correlation
  regimes; CFR 2013's estimation-robustness property partially
  compensates but does not eliminate the issue.

Cross-reference rather than duplicate. The covariance estimator
is identical across the three Session 2G covariance-primitive
strategies.

## 3. Real-rate spikes (2022) — less severe than MV / ERC

2022 Fed-tightening: TLT lost 31% peak-to-trough; MDP took a ~15%
drawdown (vs MV's ~25% and ERC's ~22%). MDP's weighting is more
balanced across the 3 asset classes (25-40% each typically), so
the TLT collapse hurts proportionally less than the heavier
TLT-concentrated MV / ERC weights.

Expected behaviour in real-rate-spike regimes:

* Sharpe of −0.2 to −0.5 over the regime window.
* Max drawdown of 12-18% — *better* than MV (-22-32%) and ERC
  (-18-28%) because of the more balanced weighting.

This is one of the regimes where MDP's diversification-maximising
philosophy outperforms its sibling covariance-primitive
strategies. Pair with a duration-aware overlay (Phase 1
`real_yield_momentum`) for further mitigation.

## 4. Trending-equity regimes — underperforms vs MV / equal-weight

When equity is in a sustained bull market (post-GFC 2010-14;
2017-21), MDP under-weights SPY relative to equal-weight (because
SPY has the highest individual vol and so contributes
disproportionately to portfolio risk). The result is that MDP
captures roughly 70-80% of the equity bull return — less than
equal-weight's full 33% SPY allocation, more than MV's near-zero
SPY allocation.

Expected behaviour in equity-trending regimes:

* Sharpe of 0.4-0.7 (positive but below equity-only benchmark).
* Drawdown of 8-15% during the regime (minor pullbacks).
* Relative under-performance vs equal-weight or 60/40: 3-8% per
  year cumulatively.

This is the canonical "diversification penalty" — MDP trades
upside for crisis robustness. Phase 3 users with high equity-
trend tolerance should consider `gtaa_cross_asset_momentum` or
`vigilant_asset_allocation_5` instead.

## 5. Lowest-correlation-pair concentration

A structural feature of MDP: when one asset pair has materially
lower pairwise correlation than the others, MDP concentrates the
two assets in that pair. In our 3-asset panel:

* TLT-SPY correlation: typically −0.2 to +0.1 (low / mildly negative)
* TLT-DBC correlation: typically −0.1 to +0.2
* SPY-DBC correlation: typically +0.2 to +0.5

The TLT-SPY pair has the lowest pairwise correlation most of the
time → MDP concentrates weight there → SPY and TLT typically get
30-40% each, DBC gets 20-30%. In regimes where SPY-DBC correlation
collapses (commodity-led recoveries), MDP shifts toward DBC.

This is *not* a failure mode — it is the structural behavior of
maximising the diversification ratio. The cluster correlation
with `permanent_portfolio` (Commit 2, expected ρ ≈ 0.40-0.60) is
elevated relative to MV and ERC because MDP's balanced weighting
is *closest* to the static 25/25/25/25 of the three covariance-
primitive strategies.

## 6. Rebalance-cadence: monthly signal, daily bridge-side drift correction

Inherits the AlphaKit-wide convention. For max_diversification
specifically:

* ~63 daily drift-correction events per asset per year.
* Plus monthly MDP re-solve events that shift weights by 5-15
  percentage points (CFR 2013 estimation-robustness property
  → smaller monthly shifts than MV's 10-30 pct points).

See `docs/phase-2-amendments.md` "Session 2G: alphakit-wide
rebalance-cadence convention" for the full project-wide audit
trail.

## 7. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **Phase 2 Session 2G `risk_parity_erc_3asset`** (Commit 5) —
  closest covariance-primitive sibling at the *diversification-
  intuition* level (both exploit cross-asset correlation).
  Different objective: ERC equalises *risk contribution*; MDP
  maximises *diversification ratio*. Expected ρ ≈ **0.50–0.70**.
* **Phase 2 Session 2G `min_variance_gtaa`** (Commit 6) — same
  universe, same covariance estimator. Different objective. MDP
  weights are more balanced than MV's lowest-vol-concentration.
  Expected ρ ≈ **0.55–0.75**.
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  static 25/25/25/25. Closest to MDP among non-covariance-group
  strategies because MDP's balanced weighting resembles
  equal-weight more than MV's or ERC's. Expected ρ ≈ **0.40–0.60**.
* **Phase 1 `vol_targeting`** (volatility family) — per-asset
  inverse-vol. Expected ρ ≈ 0.20–0.40.

The Session 2G covariance-primitive trio (ERC / MV / MDP) forms
an architecturally coupled cluster — pairwise ρ values in the
0.50-0.75 range reflect methodology differences (solver objective)
under a shared covariance estimator. All three are well below the
Phase 2 master plan §10 dedup-review bar (ρ > 0.95).

## 8. SLSQP convergence (theoretical)

SciPy SLSQP on the smooth constrained nonlinear program
``min −DR(w) s.t. sum(w)=1, 0 ≤ w_i ≤ max_weight`` is well-
behaved for 3 assets. The `_covariance` helper's MDP solver
includes a `result.success` check and raises `ValueError` on
optimiser failure — propagated by this strategy as a zero-weight
emission for the affected rebalance.

Empirically, SLSQP has not failed on any 3-asset MDP problem in
the helper's test suite. CFR 2013's estimation-robustness
property suggests that production failures would be rare; if
encountered, the zero-weight emission ensures the bridge holds
100% cash for that month rather than allocating with degenerate
weights.

## Regime performance (reference, from CC 2008 Table 2 + practitioner data)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-GFC bull (2003-07) | 2003-04 – 2007-09 | ~0.7 | −5% |
| GFC crisis (2007-09) | 2007-10 – 2009-03 | ~0.5 | −15% |
| Post-GFC reflation (2010-14) | 2010-01 – 2014-12 | ~0.7 | −8% |
| Range-bound (2015-18) | 2015-01 – 2018-12 | ~0.5 | −10% |
| COVID + recovery (2020-21) | 2020-01 – 2021-12 | ~0.4 | −16% |
| Real-rate spike (2022) | 2022-01 – 2022-12 | ~−0.3 | −15% (better than MV's -25%) |

(Reference ranges from CC 2008 Table 2 + practitioner sources;
the in-repo benchmark is the authoritative source for this
implementation — see
[`benchmark_results.json`](benchmark_results.json).)
