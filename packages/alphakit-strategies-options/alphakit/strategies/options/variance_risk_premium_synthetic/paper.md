# Paper — Variance Risk Premium Synthetic (Bondarenko 2014 / Carr-Wu 2009)

## Citations

**Initial inspiration:** Bondarenko, O. (2014). **Why Are Put
Options So Expensive?** *Quarterly Journal of Finance*, 4(1),
1450015.
[https://doi.org/10.1142/S2010139214500050](https://doi.org/10.1142/S2010139214500050)

Bondarenko documents the variance risk premium empirically and
provides the foundation for VRP-harvesting strategies. The
short-volatility position systematically earns a positive
premium across S&P 500 horizons.

**Primary methodology:** Carr, P. & Wu, L. (2009). **Variance
Risk Premia.** *Review of Financial Studies*, 22(3), 1311-1341.
[https://doi.org/10.1093/rfs/hhn038](https://doi.org/10.1093/rfs/hhn038)

Carr-Wu §2 derives the model-free **variance-swap-replication
formula**: a strike-weighted portfolio of OTM puts and calls
(with weights ∝ 2/K²) replicates the variance swap rate in
continuous time. This is the canonical model-free approach to
isolating variance exposure without delta hedging dependence.

BibTeX entries: `bondarenko2014puts` (foundational) and
`carrWu2009vrp` (primary).

## Why two papers

Bondarenko (2014) provides the *empirical* evidence for the
variance risk premium. Carr-Wu (2009) provides the *theoretical
methodology* for replicating variance exposure analytically. The
strategy *replicates* Carr-Wu's setup (in approximated form);
we cite Bondarenko as the foundational empirical reference.

## Implementation: a 2-leg approximation

The full Carr-Wu §2 replication uses an **integral over the
strike grid** with weights ∝ 2/K². The synthetic chain provides
9 strikes spanning 0.80×–1.20× spot — a coarse grid that doesn't
support the integral cleanly. This strategy ships a **simpler
2-leg approximation**: short ATM call + short ATM put (= short
ATM straddle), which captures the at-the-money portion of the
variance-swap-replicating portfolio.

Honestly documented as an *approximation* in the spirit of the
variance-swap formula, not a literal replication. The full
multi-strike replication is deferred to Phase 3 with Polygon
(denser strike grid + dynamic weight computation).

## Differentiation from siblings

* vs `delta_hedged_straddle` (Commit 9, ρ ≈ -0.7 to -0.9):
  This strategy is the **short** side of the same straddle —
  opposite VRP direction. Expected POSITIVE return per Carr-Wu's
  short-vol-earns-VRP result; the long version
  (`delta_hedged_straddle`) loses on average.
* vs `gamma_scalping_daily` (Commit 10, ρ ≈ -0.7 to -0.9):
  Same opposite-side relationship. `gamma_scalping_daily` is
  Sinclair-framed long-vol; this is Carr-Wu-framed short-vol.
* vs `short_strangle_monthly` (Commit 7, ρ ≈ 0.85-0.95):
  Same direction (short-vol) with ATM strikes vs 10 % OTM
  strikes. ATM strikes capture more premium per cycle but
  bear more tail risk (closer to spot at write).
* vs `bxm_replication` (Commit 4, ρ ≈ 0.70-0.85):
  Both ATM-strike monthly writes; bxm_replication adds long
  underlying (covered call), this is naked short straddle.
* vs `covered_call_systematic` (Commit 2, ρ ≈ 0.55-0.75):
  Covered call is single-leg + equity beta; this is 2-leg
  pure-options.

## Bridge integration: 2 short-leg discrete dispatch

Composition wrapper combining
`CoveredCallSystematic(otm_pct=0.0)` and
`CashSecuredPutSystematic(otm_pct=0.0)` — both at ATM strikes.
The strategy declares ``discrete_legs = (call_leg_symbol,
put_leg_symbol)``; the bridge applies ``Amount`` semantics to
both option legs and ``TargetPercent`` (default) to the
underlying — but the strategy emits ``0.0`` weight on the
underlying (pure-options trade).

Cross-reference: `docs/phase-2-amendments.md` 2026-05-01 "bridge
architecture extension for discrete-traded legs".

## Published rules (Carr-Wu §2 ATM approximation, monthly)

For each first trading day of a calendar month *t*:

1. **Short ATM call.** Strike = `closest_chain_strike(spot_t)`
   (= 1.00× spot grid point on the synthetic chain).
2. **Short ATM put.** Strike = same ATM strike (the short
   straddle).
3. **Expiry.** First chain expiry > 25 days from write — same
   for both legs.
4. **Position.** Both short legs simultaneously, no underlying
   position (pure-options trade). Hold through expiry; on the
   next first-trading-day-of-month, write a fresh ATM straddle.
5. **Weights output.** ``0.0`` underlying every bar (pure-
   options trade). Both legs: ``-1.0`` on writes, ``+1.0`` on
   closes (Amount via `discrete_legs`).

## Data Fidelity

* **Multi-strike replication approximated as 2-leg ATM
  straddle.** The full Carr-Wu §2 replication weighted across
  all OTM strikes is not implementable on the synthetic chain's
  9-strike grid without significant approximation. The 2-leg
  ATM-straddle approximation captures the *direction* of the
  trade (short variance) but not the *strike-weighted purity*
  of the formal variance swap.
* **Standard substrate caveats** (flat IV, no bid-ask, single
  risk-free rate) apply.

For the **ATM** strike specifically, the synthetic chain's
flat-IV-across-strikes substrate is *closest to truth* (real
ATM IV is the kink of the smile). This makes the 2-leg ATM
approximation more substrate-faithful than OTM-leg variants.

Real-feed verification with full multi-strike replication is
deferred to Phase 3 with Polygon (ADR-004 stub).

## Expected synthetic-chain Sharpe range

**Mode 1 (full short ATM straddle):** `0.4-0.7` per Bondarenko
2014 — short ATM straddles are well within the VRP-harvesting
band, with similar Sharpe to the OTM strangle but more
premium per cycle.

**Mode 2 (degenerate underlying-only):** all-zero weights, no
trade.
