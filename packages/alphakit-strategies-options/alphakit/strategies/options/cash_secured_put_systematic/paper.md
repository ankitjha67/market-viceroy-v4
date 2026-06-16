# Paper — Systematic Cash-Secured Put (Whaley 2002 / Israelov-Nielsen 2014)

## Citations

**Initial inspiration:** Whaley, R. E. (2002). **Return and risk
of CBOE Buy Write Monthly Index.** *Journal of Derivatives*, 10(2),
35-42. [https://doi.org/10.3905/jod.2002.319188](https://doi.org/10.3905/jod.2002.319188)

The CBOE PUT index (cash-secured put-write index) is the
put-counterpart of BXM, constructed in parallel by CBOE on the
basis of Whaley's BXM methodology. The same systematic monthly
write rule, the same deterministic non-discretionary roll
schedule, applied to puts instead of calls.

**Primary methodology:** Israelov, R. & Nielsen, L. N. (2014).
**Covered call strategies: One fact and eight myths.** *Financial
Analysts Journal*, 70(6), 23-31. [https://doi.org/10.2469/faj.v70.n6.5](https://doi.org/10.2469/faj.v70.n6.5)

Israelov & Nielsen's three-factor decomposition (equity beta +
short volatility + implicit short put) is *put-call parity*: a
covered call (long underlying + short call) has the same payoff
ex-dividends as ``+cash − short put`` at the same strike and
expiry. PUT-style cash-secured-put-writes earn the same variance
risk premium as BXM-style covered calls, with mechanically simpler
exposure.

BibTeX entries are aggregated in `docs/papers/phase-2.bib` under
`whaley2002bxm` (foundational) and `israelovNielsen2014covered`
(primary) — both registered alongside the
``covered_call_systematic`` commit and reused here.

## Why two papers

Whaley (2002) is the seminal *index construction* paper; CBOE PUT
applies the same construction to puts. Israelov-Nielsen (2014)
provides the put-call parity decomposition that motivates this
strategy as the put-side equivalent of
``covered_call_systematic``. We anchor the implementation on
Israelov-Nielsen because that is the paper whose decomposition the
strategy *replicates*; we cite Whaley 2002 as the foundational
index-construction reference.

## Differentiation from Phase 1 `cash_secured_put_proxy`

Phase 1's `cash_secured_put_proxy` (volatility family, ADR-002
_proxy suffix) is anchored on Ungar & Moran (2009) as a
**realized-vol overlay** — the same proxy mechanic Phase 1 uses
for `covered_call_proxy`. It does *not* consume an option chain.

Phase 2's `cash_secured_put_systematic` consumes a real
`OptionChain` from the synthetic-options adapter (ADR-005). It
expresses its position in two columns — implicit cash collateral
(the underlying held inactive) plus a real short-put leg priced
from the chain.

Both slugs co-exist on main: the proxy is the Phase 1
realized-vol-based approximation; the systematic version is the
canonical Phase 2 form.

Expected cluster correlation with the Phase 1 proxy: ρ ≈ 0.85-0.95
in neutral-to-rising-vol regimes; lower (0.5-0.7) in
strong-trending regimes. Documented in `known_failures.md`.

## Differentiation from sibling `covered_call_systematic`

**Put-call parity equivalence.** Long underlying + short call has
the same payoff (ex-dividends, European exercise) as
+cash − short put when the strikes and expiries match. The
synthetic chain prices both legs off the same Black-Scholes
diffusion, so on synthetic data the two strategies' P&L is
near-identical in *magnitude* — only the leg construction differs.

Expected cluster correlation: ρ ≈ 0.95-1.00 with
`covered_call_systematic`. Both ship as canonical Phase 2 forms
because:

* Real markets have skew; covered-call OTM-call writes capture
  a different premium from CSP OTM-put writes when skew is
  non-flat. The synthetic chain hides this difference; real-feed
  verification (Phase 3) will surface it.
* Margin treatment, capital efficiency, and compliance constraints
  may dictate one expression over the other in production
  deployments.
* The two Sharpe estimates serve as cross-validation: any
  divergence on synthetic data flags a substrate or
  implementation bug.

## Bridge integration: `discrete_legs` metadata

Same dispatch mechanism as `covered_call_systematic` — see that
strategy's `paper.md` Bridge Integration section for the canonical
explanation. The synthetic short-put leg is written-and-held for
~30 days, declared in `discrete_legs = (put_leg_symbol,)`; the
`vectorbt_bridge` dispatches `SizeType.Amount` for the leg via
`alphakit.core.protocols.get_discrete_legs`.

Cross-reference: `docs/phase-2-amendments.md` 2026-05-01 entry
"bridge architecture extension for discrete-traded legs".

## Published rules (Israelov & Nielsen 2014, PUT-aligned)

For each first trading day of a calendar month *t*:

1. **Strike.** ``K = closest_chain_strike(spot_t × (1 - otm_pct))``
   — default `otm_pct = 0.05`. Snap to the *largest* available
   chain strike ≤ `spot × 0.95` (closest-OTM-put on the grid).
2. **Expiry.** First chain expiry strictly later than 25 days
   from the write date.
3. **Position.** Cash collateral on the underlying long, short 1
   unit of the put. Hold through expiry; on the next
   first-trading-day-of-month, write a fresh put.
4. **Weights output.** `+1.0` underlying every bar (cash
   collateral expressed via TargetPercent). Put leg: `-1.0` on
   each write bar, `+1.0` on each close bar, `0.0` elsewhere
   (Amount via `discrete_legs`).

The premium series of the synthetic short-put leg is constructed
by `CashSecuredPutSystematic.make_put_leg_prices(underlying_prices,
chain_feed=…)`, which mirrors `covered_call_systematic`'s
`make_call_leg_prices` with the strike-direction reversed and
`bs.put_price` replacing `bs.call_price`.

## Data Fidelity (mandatory note for all Session 2F strategies)

The Phase 2 default options feed is the **synthetic-options
adapter** (ADR-005). Limitations:

* **Flat IV across strikes** (no skew). Real PUT writes are
  typically deep-OTM (5-10 %) where put-skew makes the premium
  materially higher than ATM-IV-priced; the synthetic chain
  underprices these writes by ~5-15 % in moderate-skew regimes.
* **No bid-ask spread / financing model.** Real CSPs face
  bid-ask drag plus margin-financing on the cash collateral
  reserved for assignment.
* **No volume / open interest.** Liquidity-weighted strategies
  cannot test capacity faithfully.
* **Single risk-free rate.** Phase 2 uses `r = 4.5 %` as a
  constant; Phase 3 will source FRED's 3-month T-bill yield per
  as-of date.

Real-feed verification with full IV skew (which is the *largest*
limitation for put writes specifically) is deferred to Phase 3
with the Polygon adapter (ADR-004 stub).

## Expected synthetic-chain Sharpe range

**Mode 1 (full CSP, end-to-end through bridge with discrete_legs
dispatch):** `0.4-0.7` on the PUT-style OOS literature (CBOE PUT
index reports 0.5-0.6 over the same windows where BXM reports
0.4-0.5 — PUT historically slightly outperforms BXM on
risk-adjusted basis, attributable to the fatter left tail of
realized SPX returns making put-write premia richer than
call-write premia).

**Mode 2 (buy-and-hold approximation, standard benchmark
runner):** SPY-fixture buy-and-hold range (Sharpe 0.3-0.5 on the
Session 2D/2E synthetic fixture data).
