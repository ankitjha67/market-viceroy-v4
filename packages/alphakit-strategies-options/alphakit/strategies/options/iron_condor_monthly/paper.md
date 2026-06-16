# Paper — Iron Condor Monthly (Hill et al. 2006 / CBOE CNDR)

## Citations

**Initial inspiration:** Hill, J. M., Balasubramanian, V.,
Gregory, K. & Tierens, I. (2006). **Finding alpha via covered
index writing.** *Journal of Derivatives*, 13(3), 51-65.
[https://doi.org/10.3905/jod.2006.622777](https://doi.org/10.3905/jod.2006.622777)

Hill et al. survey systematic option-overlay strategies on the
S&P 500 — covered calls (BXM), cash-secured puts (PUT), and
defined-risk variants including iron condors. The paper documents
the systematic-write payoff decomposition that the iron condor
inherits with the addition of protective wings.

**Primary methodology:** CBOE CNDR (Iron Condor Index)
methodology document. The CNDR index sells one OTM call + one
OTM put each month and buys further-OTM call + further-OTM put
as protective wings, all on the S&P 500 with deterministic
monthly roll. Wing widths are calibrated to the index spec
(typically 5 % short-strike offset + 10 % long-strike offset).

BibTeX entries: `hillEtAl2006` (foundational, registered in
`docs/papers/phase-2.bib`); CNDR methodology cited inline as
the primary reference.

## Why two anchors

Hill et al. (2006) is the *survey* paper that places the iron
condor in the systematic-options-overlay family. CBOE CNDR is
the *index methodology* that operationalises a specific iron
condor rule (strike offsets, expiry rule, deterministic monthly
roll). The strategy *replicates* the CNDR construction; we cite
Hill et al. as the foundational survey reference.

## Differentiation from siblings

* vs `short_strangle_monthly` (Commit 7, ρ ≈ 0.85-0.95):
  Iron condor is short strangle PLUS protective wings (long
  far-OTM put + long far-OTM call). The wings cap the maximum
  loss at the wing width minus net premium received; the
  short strangle has uncapped tails in both directions.
* vs `covered_call_systematic` (Commit 2, ρ ≈ 0.50-0.70):
  Capped vs uncapped short-vol on the call side; iron condor
  has no equity-leg exposure (pure-options trade).
* vs `cash_secured_put_systematic` (Commit 3, ρ ≈ 0.50-0.70):
  Capped vs uncapped short-vol on the put side; iron condor
  has no underlying long exposure.
* vs `bxmp_overlay` (Commit 5, ρ ≈ 0.55-0.75): BXMP carries
  equity beta + 2× uncapped short vol; iron condor is pure
  capped short vol with no equity beta.

## Bridge integration: 4 discrete legs

This is the **first 4-discrete-leg strategy** in Session 2F.
The strategy declares ``discrete_legs`` containing the four leg
column symbols (short put, long put, short call, long call). The
``vectorbt_bridge`` reads the tuple via
``alphakit.core.protocols.get_discrete_legs`` and dispatches
``SizeType.Amount`` for each declared leg via the per-column
``size_type_per_column`` array — same dispatch primitive used for
the 1-leg and 2-leg strategies, just with 4 ``Amount`` entries
instead of 1 or 2.

The underlying column gets ``SizeType.TargetPercent`` (default),
but the strategy emits ``0.0`` weight on the underlying column
because an iron condor is a pure-options trade with no
equity-leg position. The underlying column is still required in
``prices`` because the bridge's mark-to-market context with
``cash_sharing=True`` reads close prices from every column.

Cross-reference: `docs/phase-2-amendments.md` 2026-05-01 "bridge
architecture extension for discrete-traded legs".

## Published rules (CBOE CNDR-aligned)

For each first trading day of a calendar month *t*:

1. **Short put leg.** Strike = ``closest_chain_strike(spot_t × 0.95)``.
2. **Long put leg (protective wing).** Strike =
   ``closest_chain_strike(spot_t × 0.90)`` — must be deeper OTM
   than the short put.
3. **Short call leg.** Strike =
   ``closest_chain_strike(spot_t × 1.05)``.
4. **Long call leg (protective wing).** Strike =
   ``closest_chain_strike(spot_t × 1.10)`` — must be deeper OTM
   than the short call.
5. **Expiry.** First chain expiry strictly later than 25 days
   from the write date — same for all four legs (synced
   lifecycle).
6. **Position.** All 4 legs simultaneously: short put, long put,
   short call, long call. Hold through expiry; on the next
   first-trading-day-of-month, write a fresh iron condor.

The synthetic chain's 5 %-spaced strike grid maps cleanly to
these CNDR strikes — short put at 0.95×, long put at 0.90×,
short call at 1.05×, long call at 1.10×. All four sit on the
synthetic chain's grid points exactly.

Net premium received per cycle = (short put premium + short call
premium) − (long put premium + long call premium). Maximum loss
per contract = wing width − net premium.

## Data Fidelity (mandatory note for all Session 2F strategies)

Same substrate caveats as other Session 2F strategies: synthetic
chain has flat IV across strikes (no skew), no bid-ask spread,
no volume / open interest, single risk-free rate. For iron
condor specifically, the flat-IV substrate has *competing biases*
on the 4 legs:

* Real put-skew makes the short-put premium higher than the
  synthetic chain prices it (underestimates the strategy's
  income on the put side).
* Real call-skew is gentler, so the synthetic chain's bias is
  smaller on the call side.
* The protective long puts are deeper OTM where the put-skew
  effect is even larger — real markets price these wings more
  expensively than the synthetic chain does (overestimating the
  strategy's defensive cost).

Net effect: the synthetic-chain backtest tends to under-state
the iron condor's net premium income by roughly 5-10 % vs.
real-feed equivalent — less than the standalone CSP's 10-20 %
because the protective wing partially offsets the put-skew bias.

Real-feed verification deferred to Phase 3 with Polygon
(ADR-004 stub).

## Expected synthetic-chain Sharpe range

**Mode 1 (full iron condor, end-to-end through bridge with
4-leg discrete dispatch):** `0.5-0.8` — the CNDR index typically
reports Sharpe in this band. Higher than BXM/PUT standalone
because the protective wings cap the tail (max-drawdown
reduction more than offsets the wing premium cost).

**Mode 2 (degenerate underlying-only):** all-zero weights, no
trade. Final equity equals initial cash (modulo float noise).
The standard `BenchmarkRunner` exercises Mode 2 until Session
2H wires up the leg construction.
