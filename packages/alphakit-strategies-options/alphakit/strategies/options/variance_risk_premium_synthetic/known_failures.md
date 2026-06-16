# Known failure modes — variance_risk_premium_synthetic

> Phase 2 short-vol VRP harvest via 2-leg ATM-straddle
> approximation. Bondarenko 2014 foundational + Carr-Wu 2009 §2
> primary. The strategy will lose money in the regimes below;
> none are bugs — they are the cost of the variance-risk-premium
> exposure (which on average earns a positive premium per
> Bondarenko / Carr-Wu).

## 1. Sharp directional moves (any direction)

Short ATM straddle has uncapped tails in both directions.
Single-month moves of >5 % in either direction produce
assigned-leg losses that exceed the per-cycle premium
(typically $1-$3 on $100 underlying). Losses compound in
sustained-trend regimes.

Expected behaviour:

* Single-cycle losses of $5-$15 per contract on sustained
  monthly moves of 5-15 %.
* Multi-month directional trends produce 3-5 consecutive losing
  cycles; cumulative drawdown 12-20 %.

## 2. Vol-of-vol spikes

Same severity as `short_strangle_monthly` and
`bxmp_overlay` — vol expansion produces large mark-to-market
losses on both short legs. Drawdown 8-15 % from peak in spike
weeks.

Real put-skew widening during stress is *not* captured by the
synthetic chain's flat-IV substrate, so the synthetic backtest
*understates* the real-world drawdown by 3-5 percentage points.

## 3. 2-leg-approximation caveat (CRITICAL)

This is **not** a literal Carr-Wu §2 variance-swap replication.
The full replication uses a strike-weighted portfolio across
the entire OTM put + OTM call strike grid. This strategy
approximates with a 2-leg ATM straddle.

Implications:

* The strategy's P&L tracks the *level* of the variance risk
  premium but not its *strike-conditional purity*. Real
  variance-swap-replicating portfolios are much closer to
  pure variance exposure than this 2-leg approximation.
* The ATM-only construction is most exposed to **at-the-money
  vol** specifically. Skew-driven VRP variations are not
  captured.

The 2-leg approximation is the correct ship target for Phase 2
given the synthetic chain's 9-strike grid (5 %-spaced). The full
multi-strike replication waits on Phase 3 with Polygon (denser
grid + computed 2/K² weights).

## 4. Cluster overlap with siblings

* **`short_strangle_monthly`** (Commit 7): ρ ≈ 0.85-0.95.
  Same trade direction with ATM strikes (vs 10 % OTM). More
  premium per cycle, more tail risk.
* **`bxm_replication`** (Commit 4): ρ ≈ 0.70-0.85. Both
  ATM-strike monthly writes; bxm_replication adds long
  underlying.
* **`bxmp_overlay`** (Commit 5): ρ ≈ 0.75-0.85. BXMP is
  short straddle + long underlying; this is short straddle
  only.
* **`delta_hedged_straddle`** (Commit 9): ρ ≈ -0.7 to -0.9
  (opposite VRP direction).
* **`gamma_scalping_daily`** (Commit 10): ρ ≈ -0.7 to -0.9
  (opposite VRP direction).

## 5. Composition-wrapper transparency

`VarianceRiskPremiumSynthetic` uses 2 inner strategy instances
(`CoveredCallSystematic(otm_pct=0)` and
`CashSecuredPutSystematic(otm_pct=0)`). Bug fixes flow through
automatically.

The composition wrapper's behaviour required relaxing
`CashSecuredPutSystematic`'s ``otm_pct`` validation from
``> 0`` to ``>= 0`` so that ``otm_pct = 0.0`` (ATM) is allowed
as a parametric variant. Documented in the corresponding
strategy's test_unit.py.

## 6. Standard-benchmark-runner mode caveat (degenerate)

Same as siblings.

## 7. OTM-expiry close approximation

Same as siblings (×2 legs).

## 8. Calendar-month-start writes vs. third-Friday writes

Same convention as siblings.

## 9. yfinance passthrough assumption (Session 2H verification)

Inherited from sibling strategies.
