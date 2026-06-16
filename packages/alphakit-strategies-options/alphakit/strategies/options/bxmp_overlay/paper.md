# Paper — BXMP Overlay (Whaley 2002 / Israelov-Nielsen 2014, reframed wheel)

## Reframe context

This strategy is the **academic reframe** of the practitioner
"wheel" trade — see
[`docs/phase-2-amendments.md`](../../../../../../docs/phase-2-amendments.md)
2026-05-01 entry "reframe wheel_strategy → bxmp_overlay". The
wheel runs an assignment-conditional state machine (sell CSP →
take assignment → sell covered call → take assignment → restart)
which has no peer-reviewed citation. CBOE BXMP combines the BXM
and PUT index methodologies *simultaneously* each month rather
than alternating, making it a citable systematic counterpart with
the same economic content.

## Citations

**Initial inspiration:** Whaley, R. E. (2002). **Return and risk
of CBOE Buy Write Monthly Index.** *Journal of Derivatives*, 10(2),
35-42. [https://doi.org/10.3905/jod.2002.319188](https://doi.org/10.3905/jod.2002.319188)

CBOE BXMP combines the ATM call write rule of BXM (Whaley 2002)
with the cash-secured put write rule of PUT (also Whaley
methodology). Each month: long underlying, short ATM call, short
OTM put with cash collateral.

**Primary methodology:** Israelov, R. & Nielsen, L. N. (2014).
**Covered call strategies: One fact and eight myths.** *Financial
Analysts Journal*, 70(6), 23-31. [https://doi.org/10.2469/faj.v70.n6.5](https://doi.org/10.2469/faj.v70.n6.5)

Israelov-Nielsen's three-factor decomposition (equity beta + short
volatility + implicit short put) generalises straightforwardly to
the BXMP combined book: BXMP is essentially **2× short-volatility
+ 1× equity-beta** on a single underlying, with the call write
and put write contributing the two short-vol exposures and the
underlying long providing the equity beta.

BibTeX entries: `whaley2002bxm` (foundational) and
`israelovNielsen2014covered` (primary) — both registered alongside
the `covered_call_systematic` commit and reused here.

## Why two papers

Whaley (2002) constructs BXM. CBOE later constructs PUT and BXMP
on the same methodological framework. Israelov & Nielsen (2014)
provides the variance-risk-premium / put-call-parity decomposition
that motivates the strategy — both for the standalone BXM/PUT and
for the combined BXMP book.

## Differentiation from `wheel_strategy` folklore

| Aspect | `wheel_strategy` (dropped) | `bxmp_overlay` (this strategy) |
|---|---|---|
| Construction | Sequenced put/call alternating on assignment | Simultaneous put + call writes each month |
| Citation | Folklore, no peer-reviewed paper | Whaley 2002 + Israelov-Nielsen 2014 + CBOE BXMP methodology |
| State | Path-conditional (assignment state machine) | Deterministic (calendar-month-start trigger) |
| Phase 2 status | Dropped | Reframed and shipped |

The reframe preserves the *economic content* (alternating short-put
and short-call exposure on a single underlying) while replacing
the folklore mechanic with a citable systematic rule.

## Differentiation from siblings

* vs `covered_call_systematic` (ρ ≈ 0.85-0.95): BXMP includes
  the call write and adds the put leg. Full BXMP is "BXM plus a
  put."
* vs `cash_secured_put_systematic` (ρ ≈ 0.85-0.95): BXMP
  includes the put write and adds the call leg.
* vs `bxm_replication` (ρ ≈ 0.85-0.95): BXMP shares the ATM
  call rule, adds the put.
* vs `short_strangle_monthly` (Commit 7, ρ ≈ 0.80-0.90): same
  combined short-vol exposure, different leg construction
  (strangle is a 2-leg pure-options trade with no underlying;
  BXMP is a 3-instrument book with the underlying as the third
  position).

## Bridge integration: `discrete_legs` metadata

Composition wrapper combining `CoveredCallSystematic` (ATM call,
default `call_otm_pct = 0.0`) with `CashSecuredPutSystematic`
(5 % OTM put, default `put_otm_pct = 0.05`). The strategy
declares `discrete_legs = (call_leg_symbol, put_leg_symbol)` so
the bridge dispatches `SizeType.Amount` for both option legs and
`SizeType.TargetPercent` for the underlying.

This is the first multi-discrete-leg strategy in Session 2F. The
bridge handles the per-column dispatch via the array
`size_type_per_column` it already builds in
`vectorbt_bridge.py:run` — no code change vs. single-discrete-leg
strategies. Each declared leg gets `Amount`; the underlying gets
`TargetPercent`.

Cross-reference: `docs/phase-2-amendments.md` 2026-05-01 "bridge
architecture extension for discrete-traded legs".

## Published rules (CBOE BXMP combined)

For each first trading day of a calendar month *t*:

1. **Call leg.** Per BXM: write ATM call. Strike =
   ``closest_chain_strike(spot)`` (effectively the 1.00 ×
   spot grid point on the synthetic chain).
2. **Put leg.** Per PUT-aligned: write 5 % OTM put. Strike =
   ``closest_chain_strike(spot × 0.95)``.
3. **Expiry.** First chain expiry strictly later than 25 days
   from the write date — same for both legs.
4. **Position.** Long 1 unit underlying, short 1 unit call,
   short 1 unit put (cash collateral implicit in the underlying
   long under put-call parity). Hold through expiry; on the
   next first-trading-day-of-month, write fresh call + put.
5. **Weights output.** `+1.0` underlying every bar
   (TargetPercent). Call leg + put leg: each `-1.0` on writes,
   `+1.0` on closes, `0.0` elsewhere (Amount via
   `discrete_legs`).

Both legs are written *simultaneously* on the same write date and
held through the same expiry. The state machines for call and
put are independent — each can have its own OTM/ITM-at-close
behavior.

## Data Fidelity (mandatory note for all Session 2F strategies)

Same substrate caveats as `covered_call_systematic` and
`cash_secured_put_systematic`: synthetic chain has flat IV across
strikes (no skew), no bid-ask spread, no volume / open interest,
single risk-free rate. The flat-IV substrate is *more* of an
approximation for the put leg specifically (real put-skew is
steep) than for the call leg.

For BXMP specifically, the 2× short-vol exposure means the
combined strategy has roughly 2× the short-volatility risk of
either standalone variant — the synthetic chain's understatement
of premium income is approximately additive across the two legs.

Real-feed verification deferred to Phase 3 with Polygon (ADR-004
stub).

## Expected synthetic-chain Sharpe range

**Mode 1 (full BXMP, end-to-end through bridge with discrete_legs
dispatch on both legs):** `0.4-0.7` on the BXMP-style OOS
literature. The CBOE BXMP index typically reports Sharpe in this
band (slightly higher than BXM standalone, slightly lower than
PUT standalone, with significantly lower drawdown than either due
to the diversifying short-call + short-put combination).

**Mode 2 (buy-and-hold approximation, standard benchmark
runner):** SPY-fixture buy-and-hold range (Sharpe 0.3-0.5).
