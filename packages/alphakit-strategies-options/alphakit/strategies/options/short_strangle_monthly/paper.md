# Paper — Short Strangle Monthly (Coval/Shumway 2001 / Bondarenko 2014)

## Citations

**Initial inspiration:** Coval, J. D. & Shumway, T. (2001).
**Expected option returns.** *Journal of Finance*, 56(3), 983-1009.
[https://doi.org/10.1111/0022-1082.00352](https://doi.org/10.1111/0022-1082.00352)

Coval & Shumway document the *negative expected returns* of long
straddles (and equivalently the *positive expected returns* of
short straddles / strangles). Their empirical finding is the
foundation for systematic short-volatility strategies: long-vol
positions earn negative excess returns on average, so writing
volatility (selling the position) earns a positive risk premium.

**Primary methodology:** Bondarenko, O. (2014). **Why Are Put
Options So Expensive?** *Quarterly Journal of Finance*, 4(1),
1450015. [https://doi.org/10.1142/S2010139214500050](https://doi.org/10.1142/S2010139214500050)

Bondarenko quantifies the variance risk premium across S&P 500
puts and calls and documents the systematic short-volatility
premium. The 10 % OTM strangle write — short OTM put + short
OTM call at symmetric offsets — is the canonical setup studied
in Bondarenko's empirical sections: deep enough OTM that the
short legs typically expire worthless under random-walk
realisations, wide enough to harvest meaningful premium.

BibTeX entries: `covalShumway2001` (foundational) and
`bondarenko2014puts` (primary) — both registered in
`docs/papers/phase-2.bib`.

## Why two papers

Coval-Shumway (2001) is the *empirical foundation* for the VRP
trade: long straddles lose money on average, so short straddles
make money. Bondarenko (2014) extends the analysis with stronger
identification, separates the put-side and call-side VRP
components, and quantifies the magnitude across strike offsets.
The strategy *replicates* Bondarenko's empirical setup; we cite
Coval-Shumway as the foundational reference.

## Differentiation from siblings

* vs `iron_condor_monthly` (Commit 6, ρ ≈ 0.85-0.95): Iron
  condor is short strangle PLUS protective wings (long
  far-OTM put + long far-OTM call). The wings cap the maximum
  loss at the wing width minus net premium received; the
  short strangle has uncapped tails in both directions. Higher
  expected return, higher tail risk.
* vs `bxmp_overlay` (Commit 5, ρ ≈ 0.80-0.90): BXMP is short
  strangle PLUS long underlying (3-instrument book with equity
  beta + 2× short vol). Same combined call+put short-vol with
  BXMP's underlying long position.
* vs `covered_call_systematic` (Commit 2, ρ ≈ 0.70-0.85):
  Strangle captures both call and put VRP; covered call
  captures only the call side and adds equity beta.
* vs `cash_secured_put_systematic` (Commit 3, ρ ≈ 0.70-0.85):
  Strangle captures both sides; CSP captures only the put side
  with implicit equity exposure via cash collateral.

## Bridge integration: 2 discrete legs

Same dispatch pattern as `iron_condor_monthly` minus the
protective wings. The strategy declares ``discrete_legs =
(put_leg_symbol, call_leg_symbol)`` so the bridge applies
``SizeType.Amount`` semantics to both option legs and
``SizeType.TargetPercent`` (default) to the underlying — but the
strangle emits ``0.0`` weight on the underlying because it's a
pure-options trade.

Implementation: composition wrapper using
``CashSecuredPutSystematic(otm_pct=put_otm)`` and
``CoveredCallSystematic(otm_pct=call_otm)``. Each inner
strategy's ``make_*_leg_prices`` builds one leg's premium series.

Cross-reference: `docs/phase-2-amendments.md` 2026-05-01 "bridge
architecture extension for discrete-traded legs".

## Published rules (Bondarenko 2014, 10 % OTM strangle)

For each first trading day of a calendar month *t*:

1. **Short put leg.** Strike = ``closest_chain_strike(spot_t × 0.90)``
   (10 % OTM, deeper than CSP's default 5 % OTM).
2. **Short call leg.** Strike = ``closest_chain_strike(spot_t × 1.10)``
   (10 % OTM, deeper than covered_call_systematic's default 2 %).
3. **Expiry.** First chain expiry strictly later than 25 days
   from the write date — same for both legs.
4. **Position.** Both short legs simultaneously, no underlying
   long. Hold through expiry; on the next first-trading-day-of-
   month, write a fresh strangle.
5. **Weights output.** ``0.0`` underlying every bar
   (pure-options trade). Put leg + call leg: each ``-1.0`` on
   write bars, ``+1.0`` on close bars (Amount via
   `discrete_legs`).

The synthetic chain's 5 %-spaced strike grid maps cleanly to
these strikes — short put at 0.90×, short call at 1.10×. Both
sit on grid points exactly.

## Data Fidelity (mandatory note for all Session 2F strategies)

Same substrate caveats as other Session 2F short-vol strategies.
For short strangle specifically, the 10 % OTM offset means both
legs sit deeper in the wings where:

* Real put-skew is large (real OTM puts trade richer than the
  synthetic flat-IV chain prices them) — strategy underestimates
  the put leg's premium income by ~15-25 %.
* Real call-skew is gentler — strategy underestimates the call
  leg's premium income by ~5-10 %.

Net effect: the synthetic-chain backtest tends to under-state
the short-strangle's net premium income by approximately 10-15 %
vs. real-feed equivalent. Real-feed verification deferred to
Phase 3 with Polygon (ADR-004 stub).

## Expected synthetic-chain Sharpe range

**Mode 1 (full strangle, end-to-end through bridge with 2-leg
discrete dispatch):** `0.4-0.7` per Bondarenko 2014 empirical
estimates. Higher than capped variants (iron condor) under
quiet vol regimes; lower under stress (uncapped tail).

**Mode 2 (degenerate underlying-only):** all-zero weights, no
trade. Final equity = initial cash.
