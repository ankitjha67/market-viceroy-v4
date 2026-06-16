# Known failure modes — risk_parity_erc_3asset

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

MRT (2010) Equal-Risk-Contribution on a 3-asset stocks / bonds /
commodities panel (SPY / TLT / DBC). First consumer of the shared
``_covariance`` helper module — failure modes specific to the
covariance estimator + solver are documented below alongside the
broader strategy-level failure modes.

## 1. Real-rate spikes (2022)

When real interest rates rise sharply, **both** the TLT leg AND
the DBC leg can lose simultaneously, leaving only SPY to prop up
the portfolio. The 2022 Fed-tightening cycle illustrated this
acutely: TLT lost 31% peak-to-trough, DBC fell 15-20%, SPY fell
18% — all three legs of the ERC book went negative simultaneously
and the portfolio took a ~22% drawdown.

The ERC weighting actually *amplifies* this regime because TLT
gets the largest weight (long-duration is the lowest-vol leg most
of the time, so ERC over-weights it). When TLT collapses, the
portfolio takes the full loss on the largest position.

Expected behaviour in real-rate-spike regimes:

* Sharpe of −0.4 to −0.7 over the regime window.
* Max drawdown of 18–28% (the strategy's worst-case regime).

Mitigation: pair with a duration-aware overlay (Phase 1
`real_yield_momentum` rates family, or Session 2G
`growth_inflation_regime_rotation`).

## 2. Covariance-estimation failure modes (first user of `_covariance` helper)

This strategy is the **first consumer** of the package-private
``_covariance`` helper. The helper has comprehensive test
coverage (41 tests including analytic-known-result anchors) but
the production failure modes specific to live data:

**Constant-price legs trigger ValueError.** If any one of the
three legs has zero realized variance over the rolling window
(e.g. a temporary trading halt causing constant close prices),
the ``solve_erc_weights`` solver raises ``ValueError`` and this
strategy emits zero weights at that rebalance (the bridge holds
100% cash). Next rebalance, if variance has returned to normal,
the strategy resumes ERC weighting.

This is *not* a bug — it is the helper's deliberate fail-loud
behavior on degenerate inputs. The alternative (silently allocating
to a zero-variance asset) would mis-state the portfolio's risk
exposure.

**Rolling-window edge case.** Before 252 trading days of history
are available, the rolling covariance is undefined and the
strategy emits zero weights everywhere. This is documented in the
strategy's edge-case docstring.

**Ledoit-Wolf shrinkage intensity.** Default α (analytic-optimal
to a constant-correlation target) is typically 0.1-0.3 on the
3-asset 252-day window. In high-correlation regimes (2020 March
when all asset classes were briefly correlated), α can spike to
0.5-0.7 — the shrinkage pulls the covariance toward an unrealistic
constant-correlation target. The ERC solver still converges but
the weights are less responsive to real correlation structure.

Mitigation: switch to ``shrinkage="none"`` via the constructor
parameter for users who prefer raw sample covariance.

## 3. Single-asset vol spikes overweight low-vol legs

A core failure mode of ERC: when one asset's volatility spikes
(typically equities during a crisis), ERC reduces that asset's
weight and *over-weights* the remaining lower-vol assets. In a
crisis where bond vol *also* spikes (rates moving with equities),
this means ERC bunches into the lowest-vol leg — typically TLT.

2008 GFC: SPY 6-month realized vol jumped from 16% to 45% in
September 2008. ERC reduced SPY weight from 28% to 12% and
increased TLT weight from 38% to 52% — concentration into one
leg.

Expected behaviour in equity-vol-spike regimes:

* ERC under-weights equity at exactly the wrong time (post-crash
  recovery is when SPY's 6-month forward returns are highest).
* Sharpe of 0.2-0.4 in the 6 months post-crash vs ~0.7-1.0 for
  equity-heavier allocators (like permanent_portfolio's static
  25% equity weight).

This is a *cost of the methodology* — the ERC weighting cannot
distinguish between "high vol → low forward return" (typical
times) and "high vol → high forward return" (post-crash). It is
not a bug.

## 4. Long-duration bond-leg substitution (TLT vs AGG)

Strategy uses TLT (20+ year Treasuries, ~17-year duration) as the
bond leg. The textbook risk-parity construction often uses AGG
(US aggregate, ~6-year duration) or intermediate Treasuries. With
AGG, ERC weights collapse into ~75% AGG / 12% SPY / 13% DBC —
geometric concentration in the lowest-vol asset.

The TLT choice rebalances the cross-asset risk contributions
(weights roughly 30-45% TLT / 25-35% SPY / 25-35% DBC) but
introduces a structural long-duration tilt that AGG would not
have. The bond-leg sensitivity to rates is materially higher than
the textbook risk-parity setup.

Phase 3 users with intermediate-duration appetites should
construct a substituted variant via the ``bonds_symbol``
constructor parameter (``RiskParityErc3Asset(bonds_symbol="AGG")``).

## 5. Rebalance-cadence: monthly signal, daily bridge-side drift correction

This strategy inherits the AlphaKit-wide convention: monthly
target signal emitted at month-end, daily bridge-side drift
correction by vectorbt's ``SizeType.TargetPercent`` semantics.
Empirical trade-event count: **~63 events per asset per year**
(drift correction) + monthly ERC re-solve events that may shift
weights by 5-15% per leg.

Per-trade notional is small (daily drift correction) plus the
monthly re-solve shift; total commission cost is bounded under
any reasonable per-trade model. For the full project-wide audit
trail of the cadence convention, see
``docs/phase-2-amendments.md`` "Session 2G: alphakit-wide
rebalance-cadence convention".

## 6. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  closest cluster sibling. Both are multi-asset
  static / quasi-static allocators that over-weight low-vol
  assets. The difference is that ERC adapts to *realized*
  covariance while permanent_portfolio is fixed 25/25/25/25.
  Expected ρ ≈ **0.60–0.75** — well below the Phase 2 master
  plan §10 deduplication-review bar (ρ > 0.95) but documented as
  a deliberate family pair. The cluster overlap is the largest in
  the Session 2G family and is the trade-off of having two
  multi-asset allocators that both target balanced risk exposure.
* **Within Session 2G covariance-primitive group (same `_covariance`
  helper):**
  - `min_variance_gtaa` (Commit 6) — different objective (min
    variance). Same covariance estimator. Expected ρ ≈ 0.55–0.75.
  - `max_diversification` (Commit 7) — different objective (max
    DR). Same covariance estimator. Expected ρ ≈ 0.50–0.70.
  These three Session 2G strategies form an architecturally
  coupled trio — their pairwise correlations reflect *methodology*
  differences (ERC vs MV vs MDP objectives) under a *shared*
  covariance estimator.
* **Phase 1 `vol_targeting`** (volatility family) — single-asset
  inverse-vol scaling. Expected ρ ≈ 0.20–0.40.
* **Phase 1 `dual_momentum_gem`** (trend family) — discrete
  momentum rotation. Expected ρ ≈ 0.20–0.40.
* **Phase 2 Session 2G `gtaa_cross_asset_momentum`** (Commit 3) —
  continuous TSMOM on broader universe. Expected ρ ≈ 0.30–0.50.

## 7. Solver convergence (theoretical)

The Spinu (2013) convex reformulation
(``min  ½ wᵀΣw − (1/N) Σᵢ log(wᵢ)``) is strictly convex in *w* —
L-BFGS-B converges to the global optimum under positive box
bounds. Empirically the helper's analytic-anchor test (3
uncorrelated assets with vols 10% / 20% / 30% → weights
proportional to inverse vol) passes within atol=1e-5. Production
convergence failures would be unprecedented for a 3-asset problem
of this size; the helper raises ``ValueError`` if scipy
``L-BFGS-B`` reports ``result.success = False``, and this
strategy propagates the failure as an emitted zero weight at the
affected rebalance.

## Regime performance (reference, from AFP 2012 Table 2 + practitioner data)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-GFC bull (2003-07) | 2003-04 – 2007-09 | ~0.9 | −6% |
| GFC crisis (2007-09) | 2007-10 – 2009-03 | ~0.4 | −20% |
| Post-GFC reflation (2010-14) | 2010-01 – 2014-12 | ~0.8 | −10% |
| Range-bound (2015-18) | 2015-01 – 2018-12 | ~0.5 | −12% |
| COVID + recovery (2020-21) | 2020-01 – 2021-12 | ~0.7 | −15% |
| Real-rate spike (2022) | 2022-01 – 2022-12 | ~−0.6 | −22% |

(Reference ranges from AFP 2012 Table 2 + practitioner sources;
the in-repo benchmark is the authoritative source for this
implementation — see
[`benchmark_results.json`](benchmark_results.json).)
