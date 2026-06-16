# Known failure modes — bxmp_overlay

> Phase 2 reframe of practitioner "wheel" — see
> `docs/phase-2-amendments.md` 2026-05-01 entry. CBOE BXMP-aligned
> monthly call-write + put-write overlay on a single underlying.

The strategy has **2× short-volatility exposure** (call + put
both shorted) so vol-spike regimes hit harder than single-leg
covered-call or cash-secured-put strategies. None of the regimes
below are bugs — they are the cost of the combined VRP harvest.

## 1. Whipsaw rallies + selloffs (2018, 2020 March, 2022 H1)

When the underlying whipsaws — sharp rally one month, sharp drop
the next — both legs lose:

* Rally month: call leg is assigned ITM (write loses), put leg
  expires OTM (write keeps premium, partial offset)
* Drop month: put leg is assigned ITM (write loses), call leg
  expires OTM (write keeps premium, partial offset)

Per-month P&L is asymmetric in volatile regimes: the assigned-leg
loss tends to dominate the held-leg premium when moves exceed the
strike offset.

Expected behaviour for `bxmp_overlay` in similar regimes:

* Sharpe 0.0 to -0.3 in trending whipsaw markets
* Drawdown 5-15 % from peak per cycle of whipsaws
* Recovery dynamics: BXMP recovers when realized vol falls below
  IV (the short-vol premium re-asserts)

## 2. Vol-of-vol spikes (2018 February, 2020 March)

Same dynamics as `covered_call_systematic` §2 + `cash_secured_put_systematic`
§2, but **2× scaled**: both option legs see mark-to-market loss
simultaneously. Drawdown of 8-20 % from peak in the spike week
(roughly 2× the single-leg variants' 5-12 %).

The synthetic chain's flat-IV substrate *materially understates*
the BXMP drawdown in stress because real put-skew widens under
stress (PUT-side is the bigger contributor) while real call-skew
remains relatively flat. Real-feed verification (Phase 3 Polygon)
will surface this asymmetry.

## 3. Cluster overlap with siblings

* **`covered_call_systematic`** (Commit 2): ρ ≈ 0.85-0.95.
  BXMP includes the call write and adds a put.
* **`cash_secured_put_systematic`** (Commit 3): ρ ≈ 0.85-0.95.
  BXMP includes the put write and adds a call.
* **`bxm_replication`** (Commit 4): ρ ≈ 0.85-0.95. BXMP shares
  the ATM call rule, adds the put.
* **`short_strangle_monthly`** (Commit 7): ρ ≈ 0.80-0.90.
  Same combined short-vol exposure with different leg
  construction (strangle is a 2-leg pure-options trade with no
  underlying; BXMP is a 3-instrument book with the underlying as
  the third position). The strangle's no-underlying form gives
  it pure-vol exposure; BXMP carries equity beta plus 2× short
  vol.
* **`iron_condor_monthly`** (Commit 6): ρ ≈ 0.55-0.75. BXMP's
  uncapped short-vol vs iron-condor's capped tail.

## 4. Synthetic-chain substrate caveat (compounded for BXMP)

The synthetic-chain flat-IV approximation affects both legs:

* Call leg: ~5-15 % premium underestimation (per
  `covered_call_systematic` §5)
* Put leg: ~10-20 % premium underestimation (per
  `cash_secured_put_systematic` §5, MORE severe due to real
  put-skew)
* Combined: BXMP's monthly P&L on synthetic chains is
  approximately 15-30 % short of real-feed equivalent in
  moderate-skew regimes — additive across the two legs.

## 5. Standard-benchmark-runner mode caveat

Inherited from sibling strategies. Standard `BenchmarkRunner`
provides only the underlying's prices column; BXMP degrades to
long-equity buy-and-hold. The full Mode 1 BXMP P&L (3-instrument
book with both option legs) is exercised in
`tests/test_integration.py`. Session 2H benchmark-runner refactor
will wire up the leg construction.

## 6. OTM-expiry close approximation (compounded for BXMP)

The 1-2 % per-cycle approximation from
`covered_call_systematic` §7 and
`cash_secured_put_systematic` §7 applies to BOTH legs of BXMP
independently. Per-cycle P&L approximately 2-4 % short of
analytic when both legs expire OTM (both close one bar early at
small residual time-value premium).

## 7. Calendar-month-start writes vs. third-Friday writes

Same convention as siblings: first-trading-day-of-month writes
vs. published BXMP third-Friday writes. ≤ 10 % per year shift
in premium-income profile. Both legs roll on the same write
date.

## 8. yfinance passthrough assumption (Session 2H verification)

Inherited from sibling strategies.

## 9. Composition-wrapper transparency

`BXMPOverlay` is a thin composition wrapper combining
`CoveredCallSystematic` (otm_pct=0.0 default) and
`CashSecuredPutSystematic` (otm_pct=0.05 default). Bug fixes or
behavior changes to either parent flow through to this strategy
automatically.

If `CoveredCallSystematic` or `CashSecuredPutSystematic` lifecycle
algorithms change, `bxmp_overlay`'s tests must continue to pass —
enforced by the integration test running the full Mode 1
backtest end-to-end through `vectorbt_bridge.run` with both
discrete legs dispatched.

## 10. Reframe transparency (wheel_strategy → bxmp_overlay)

The Phase 2 master-plan slug `wheel_strategy` is **not** a Phase
2 strategy. The reframe to `bxmp_overlay` is documented in
`docs/phase-2-amendments.md` 2026-05-01. Users searching for
"wheel" in the Phase 2 codebase should find this strategy and
its paper.md cross-reference.

The economic content of the wheel (alternating short-put and
short-call exposure on a single underlying) is preserved; only
the *trigger logic* changed (assignment-conditional → calendar-
deterministic) and the *citation* changed (folklore → Whaley 2002
+ Israelov-Nielsen 2014 + CBOE BXMP).
