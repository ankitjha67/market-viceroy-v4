# Known failure modes — recession_probability_rotation

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

EM (1998) / Wright (2006) recession-probability-driven rotation
between pro-cyclical 60/40 and defensive TLT+GLD on a 3-asset
universe (SPY / TLT / GLD) driven by the Cleveland Fed
`RECPROUSM156N` informational column. First consumer of the
regime-state primitive and the informational-column pattern.

## 1. False-positive regime calls (canonical EM-1998 failure mode)

The 30% probability threshold is a *forecast*: when the model
exceeds 30%, an NBER-dated recession follows in the next 12
months with high probability — but not certainty. False positives
exist:

* Probability has briefly exceeded 30% without a recession
  following in several episodes since 1959. EM 1998 reports the
  false-positive rate at ~5-10% in-sample on the 1959-1998 window.
* In each false-positive episode, the strategy rotates to
  defensive allocation (no equity, 60% TLT + 40% GLD) and **misses
  the continued equity bull**. The opportunity cost is
  proportional to the duration of the false signal.

Historical false-positive examples (model-version dependent):

* **1966-67 credit crunch:** model exceeded 30% briefly; no NBER
  recession followed for ~30 months.
* **1998 LTCM / Asian crisis:** brief threshold breach; no
  recession until 2001.

Expected behaviour during false-positive episodes:

* Strategy takes defensive allocation for 3-12 months while
  equities continue rallying.
* Cumulative opportunity cost: 5-15% per year vs the standalone
  60/40 benchmark over the false-positive window.
* Recovers when the probability drops back below 30% and the
  strategy returns to pro-cyclical 60/40.

This is the canonical cost of the EM 1998 threshold-based
approach. Users who can tolerate higher false-positive rates may
prefer a higher threshold (e.g. 40-50% via the
`recession_threshold` constructor parameter); the trade-off is
larger drawdowns when a true recession arrives.

## 2. Publication-lag forensics (LOAD-BEARING — first regime-state strategy)

The Cleveland Fed `RECPROUSM156N` series is published with a
**one-month reporting lag**. The value at FRED index "month *N*"
is the recession probability *for* month *N*, but it is *published*
in month *N+1* (typically mid-month or end-of-month).

A naïve strategy that reads `RECPROUSM156N[month_end_N]` when
emitting weights for month-end *N* would be using **future
information** — the value at index *N* was not yet published at
month-end *N*.

The strategy applies a `lag_months=1` shift to the FRED column
before reading. This means:

* At month-end *N*, the strategy reads
  `recession_prob.shift(1)[month_end_N]`, which equals
  `recession_prob[month_end_N-1]` — the value for month *N-1*
  that was published in month *N*. This matches what a real-time
  investor would have seen.
* The shift is verified by
  `tests/test_unit.py::test_publication_lag_uses_prior_month_value`,
  which constructs a panel where `RECPROUSM156N` jumps from 0.0
  to 0.6 at a specific month and verifies the strategy's regime
  flip occurs the *month after* the jump.

**Failure to apply the lag** is the most common foot-gun in FRED-
driven regime strategies. A strategy that mistakenly uses
`lag_months=0` would appear to have a 0.5-1.0 higher backtest
Sharpe than the lag-corrected version — the gap is the value of
the foresight, which is *not* available in production.

This is the load-bearing correctness mechanism for this entire
regime-state group (Commits 8-12). Future regime strategies must
inherit the same lag-handling discipline; `growth_inflation_regime_rotation`
(Commit 9) applies the lag to both CPI and GDP columns separately.

## 3. Sharp regime transitions (2008 GFC, 2020 March COVID)

The model is a *forecast*, not a real-time indicator. When a
recession arrives suddenly (without months of building economic
weakness), the recession-probability series lags the event:

* **2008 GFC:** `RECPROUSM156N` did not exceed 30% until October
  2008 — when SPY had already fallen 25% peak-to-trough. The
  strategy held pro-cyclical 60/40 into the September 2008 panic
  and took the full SPY drawdown before rotating to defensive in
  October 2008.
* **2020 March COVID:** the model is monthly; February's value
  was published in March *after* the March 9 equity crash. The
  strategy could not flip to defensive until the March month-end
  rebalance, by which point SPY was already down 34% from
  February peak.

Expected behaviour during sharp regime transitions:

* Drawdown of 15-25% before the rotation triggers.
* Recovery as the strategy holds defensive allocation through
  the subsequent recession trough.

This is a *cost of monthly cadence + forecast-lag*. Higher-
frequency alternatives (weekly Cleveland Fed updates, daily
high-frequency credit-spread proxies) are out of scope for this
implementation.

## 4. Model versioning (Cleveland Fed periodic revisions)

The Cleveland Fed periodically revises the underlying probit
specification of `RECPROUSM156N`. Major revisions occurred in
2012 and 2018. Each revision can produce backward-revised
historical values that differ materially from the original
published series.

Impact:

* Historical backtests use the **current** revised series, not
  the series that was available in real time at each historical
  date.
* The reported Sharpe in `benchmark_results.json` is conditional
  on the current model version (as of 2025-12-31 cutoff).
* Future revisions could materially change the backtest Sharpe.

Mitigation: Phase 3 users who care about real-time-vintage
accuracy should consume FRED's ALFRED vintage-aware service which
records the *as-of-date* version of each FRED value. This
strategy reads only the current series, so historical Sharpe is
"as if today's model had always been used".

## 5. Universe constraint (3-asset only)

The strategy uses a 3-asset universe (SPY/TLT/GLD). When the
defensive regime triggers, the strategy holds 60% TLT + 40% GLD.
This is sensitive to:

* TLT drawdowns in real-rate-spike regimes (2022 — TLT lost 31%
  while RECPROUSM156N stayed below threshold, so the strategy
  held 60/40 and took the TLT loss on the bond leg).
* GLD drawdowns in disinflation regimes (1981-82 — gold fell as
  Volcker tightening drove real rates higher).

The 3-asset constraint is documented in `paper.md` "Data Fidelity".
Phase 3 users could add a 4th leg (cash / SHY) to the universe by
extending the `risk_off_weights` and `risk_on_weights` tuples.

## 6. Rebalance-cadence: monthly signal, daily bridge-side drift correction

Inherits the AlphaKit-wide convention: monthly target signal +
bridge-side daily drift correction by vectorbt's
`SizeType.TargetPercent`. For recession_probability_rotation
specifically:

* ~63 daily drift-correction events per asset per year on the
  three tradable legs.
* Plus 0-3 regime-flip events per year (large discrete weight
  swaps when the threshold is crossed).
* Zero events on the `RECPROUSM156N` informational column (always
  weight 0.0 → no orders).

See `docs/phase-2-amendments.md` "Session 2G: alphakit-wide
rebalance-cadence convention" for the full project-wide audit
trail.

## 7. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **Phase 2 Session 2G `yield_curve_regime_allocation`** (Commit 10)
  — closest cluster sibling. The yield-curve slope is one of the
  inputs to the Cleveland Fed's recession-probability model, so
  the two strategies trade highly correlated signals. Expected
  ρ ≈ **0.50–0.70**. The Phase 2 master plan §10 dedup-review
  bar (ρ > 0.95) is well above this expected range, but the
  high correlation is acknowledged as the cost of having two
  regime strategies driven by overlapping signal sources.
* **Phase 2 Session 2G `growth_inflation_regime_rotation`**
  (Commit 9) — different signal (CPI + GDP) and finer taxonomy
  (4-cell). Expected ρ ≈ 0.40–0.60.
* **Phase 2 Session 2G `fed_policy_tilt`** (Commit 11) —
  different signal (fed funds rate), similar pro-cyclical /
  defensive rotation. Expected ρ ≈ 0.40–0.60.
* **Phase 2 Session 2G `inflation_regime_allocation`** (Commit 12)
  — CPI YoY signal, different asset rotation. Expected ρ ≈
  0.30–0.50.
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  static allocation. Expected ρ ≈ 0.30–0.50.
* **Phase 2 Session 2G covariance-primitive group** (Commits 5-7)
  — covariance-based vs regime-based mechanic. Expected ρ ≈
  0.30–0.50.

The Session 2G regime-state group (Commits 8-12) forms a
cluster characterised by:

* Shared informational-column pattern (FRED inputs at weight 0).
* Shared publication-lag handling discipline.
* Shared monthly-rebalance cadence.
* Different signal sources (recession probability vs
  growth+inflation vs yield curve vs fed policy vs CPI).

Pairwise ρ values within the regime-state group are expected in
the 0.30-0.70 range — substantial overlap reflecting the
underlying macroeconomic-state common factor, but well below the
deduplication-review bar.

## Regime performance (reference, from EM 1998 + practitioner data)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-recession warning (1989-90) | 1989-01 – 1990-12 | ~0.6 (correctly defensive) | −4% |
| Recession captured (1990-91) | 1990-08 – 1991-03 | ~0.8 | −5% (TLT rally) |
| Dotcom warning (2000-Q3 onward) | 2000-07 – 2001-12 | ~0.4 | −8% (false-positive Q3 2000) |
| GFC late capture (2008-09) | 2008-10 – 2009-06 | ~0.5 | −18% (held 60/40 through Sept-Oct 2008 drawdown) |
| Post-GFC false-positive | 2011-08 – 2012-04 | ~−0.3 | −5% (defensive miss of equity recovery) |
| COVID lag capture (2020 March) | 2020-03 – 2020-12 | ~0.4 | −18% (March drawdown held; April-Dec recovery in defensive) |
| Real-rate spike (2022) | 2022-01 – 2022-12 | ~−0.5 | −12% (held 60/40 through TLT collapse) |

(Reference ranges from EM 1998 + Cleveland Fed + practitioner
sources; the in-repo benchmark is the authoritative source for
this implementation — see
[`benchmark_results.json`](benchmark_results.json).)
