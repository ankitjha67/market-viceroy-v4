# Known failure modes — curve_steepener_2s10s

> Slope mean-reversion is *the* canonical fixed-income trade. It is
> also the canonical fixed-income blow-up trade — every cycle has
> at least one episode where the curve stays narrow or inverted for
> longer than mean-reversion expects.

DV01-neutral 2s10s steepener with z-score entry/exit hysteresis on
the log-price spread. The strategy will lose money in the regimes
below; none of these are bugs but they are the cost of betting on
mean-reversion of a slow-moving macro variable.

## 1. Persistent inversion (1998–2000, 2006–2007, 2022–2024)

The 2s10s spread has historically inverted ahead of every US
recession since 1980, and stayed inverted for 6–24 months before
re-steepening. During inversion the z-score can pin at +2σ or
higher for a year or more, with the steepener position bleeding
DV01-neutral residual carry plus borrow cost. Re-steepening, when
it eventually arrives, often outpaces the bleed — but the holding
period is regime-length, not weeks.

Expected behaviour during a 2022-style sustained inversion:

* Steepener active for the entire inversion window
* Drawdown of 5–15% from entry to deepest inversion (residual
  carry + non-zero parallel-shift exposure due to imperfect
  duration estimates)
* Recovery that more than offsets the drawdown when the curve
  finally re-steepens, but only for traders who can hold the
  position through the inversion

Sizing implication: this is a multi-month strategy at a minimum.
Don't size it to a 1-month risk budget.

## 2. Carry burn during normal regimes

When the curve is upward-sloping (the typical regime), the
steepener position has *negative carry*: the long-leg short-end
yields less than the short-leg long-end. The position bleeds
~80–150 bps annualised on the carry alone, before transaction
and borrow costs.

The strategy enters only when the spread is *narrow* (z-score
extended), and the entry is conditional on mean-reversion. But
even when the entry is correct, the holding period during which
mean-reversion realises includes some carry-negative time. The
carry drag is part of the cost of the option.

Mitigation: tighten ``exit_threshold`` to release the position
sooner, accepting a smaller capture in exchange for less carry
drag. The default 0.25σ exit is calibrated to capture most of
the typical reversion while limiting the holding window.

## 3. Imperfect DV01 neutrality

The default duration ratio (8.0 / 1.95 ≈ 4.10) is the par-yield
ratio of constant-maturity 10Y and 2Y Treasuries. Actual durations
drift with the yield level:

* At 4% par yield: 10Y duration ≈ 8.20, 2Y duration ≈ 1.94 — close
  to the default.
* At 1% par yield: 10Y duration ≈ 9.10, 2Y duration ≈ 1.97 —
  duration ratio ≈ 4.62, so the default under-shorts the long-end
  by ~12%.
* At 8% par yield: 10Y duration ≈ 7.20, 2Y duration ≈ 1.90 —
  duration ratio ≈ 3.79, so the default over-shorts the long-end
  by ~8%.

When durations drift the position has residual parallel-shift
exposure, biasing P&L by ±duration-error × Δy_parallel. In a
50 bps parallel rally, the worst-case bias is ±20–25 bps of P&L
per unit of signal. Documented as a known failure rather than a
fix in this implementation; real-feed Session 2H benchmarks should
re-estimate durations from the ETF basket or from the FRED yield
level.

## 4. ETF basket vs constant-maturity drift (real-data only)

When run against TLT/SHY rather than constant-maturity Treasuries,
the underlying basket changes monthly as new bonds enter and old
bonds roll off. TLT's effective duration is 17, not 8; SHY's is
1.9, not 1.95. The strategy operates on log-price spreads, so the
*sign* of the signal is preserved, but the DV01-neutral weights
are wrong by a factor of ~2. The synthetic-fixture benchmark in
this folder uses constant-maturity-equivalent prices and is
unaffected by this caveat.

For real-feed Session 2H: either rescale the durations to match
the ETF basket, or substitute IEF (7-10 Year Treasury) for TLT
to keep the duration closer to 8.

## 5. Cluster correlation with other rates strategies

This strategy will exhibit ρ > 0.7 with several other rates
strategies during slope-extreme regimes:

* `curve_flattener_2s10s` — mirror-image **regime trigger**, NOT
  mirror-image signal. Both produce binary `signal ∈ {0, 1}` (not
  ±1): steepener fires only when `z > +entry_threshold`; flattener
  fires only when `z < −entry_threshold`. They trade **mutually
  exclusive z-score tail regimes** — z can't be both > +1 and < −1,
  so they never co-fire. When |z| < entry_threshold (the common
  regime, ~70% of bars), both signals are zero. Daily-return
  contributions therefore never co-occur, giving **expected ρ ≈ 0
  by construction** — NOT ρ ≈ −1.0 as earlier docs (pre-Session 2K-4)
  suggested. The S2K-4 29×29 keyed cluster empirically confirmed
  ρ = +0.000. Running both is still a documented user choice
  (covers both tail regimes); the previous "never at the same time"
  statement was correct, but the "ρ ≈ −1.0" prediction was
  inconsistent with the binary-tail mechanic and is corrected here.
* `curve_butterfly_2s5s10s` — different signal (PCA-driven on the
  2-5-10Y triplet) but overlapping when the 2s10s slope dominates
  the third PC; expected ρ ≈ 0.4–0.6
* `bond_carry_rolldown` — when the curve is steep, both the
  steepener and the rolldown trade have positive expected
  contributions from the slope; expected ρ ≈ 0.3–0.5

These overlaps are expected. The flattener pair was historically
flagged as a Phase 2 master plan §10 cluster-risk deduplication
candidate under the obsolete ρ ≈ −1.0 prediction; the S2K-4 cluster
finding (ρ = +0.000) supersedes that — they are independent
tail-regime trades, not duplicates.

## 6. Single-pair concentration risk

A 2s10s-only steepener has no protection against the level moving
without the slope (correctly hedged by DV01) or against the
curvature changing (not hedged at all). The 2s5s and 5s10s
sub-spreads can move independently, leaving the 2s10s spread
flat while the curvature changes. The steepener captures none of
the curvature P&L.

Users seeking curve-shape exposure with curvature hedging should
look at `curve_butterfly_2s5s10s`.

## Regime performance (reference, gross of fees, DV01-neutral 2s10s steepener)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Curve normalisation post-recession (2009–2010) | 2009-06 – 2010-12 | ~1.5 | −3% |
| Carry-negative steady-state (2014–2017) | 2014-01 – 2017-12 | ~−0.2 | −7% |
| Pre-recession inversion (2019) | 2019-03 – 2019-09 | ~−0.5 | −5% |
| Sustained inversion (2022–2024) | 2022-07 – 2024-09 | ~−0.8 → 1.2 | −12% then full recovery |

(Reference ranges from CTA-reported 2s10s slope sleeves and from
academic papers on slope-based prediction; the in-repo benchmark
is the authoritative source for this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
