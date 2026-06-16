# Known failure modes — bxm_replication

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

Canonical CBOE BXM index replication — exactly-ATM monthly call
write on synthetic chains. Whaley 2002 sole anchor. Composition
wrapper over `covered_call_systematic` with `otm_pct = 0.0`.

The strategy will lose money in the regimes below; none of these
are bugs, they are the cost of the variance-risk-premium exposure
on an ATM call write.

## 1. Strong sustained equity rallies

When SPY rallies sharply, the ATM call is assigned (deeper ITM
than the 2 % OTM variant), and the strategy gives up *all* upside
above the strike. This is the BXM rule's most-conservative offset
choice — the practitioner-aligned 2 % OTM variant
(`covered_call_systematic`) sacrifices some premium to participate
in the first 2 % of monthly upside. Whaley 2002 documents the
trade-off in §IV.

Expected behaviour for `bxm_replication` in strong-rally regimes:

* Sharpe 0.0 to +0.2 (vs. SPY's 1.0+ in such years; *worse* than
  `covered_call_systematic`'s +0.0 to +0.3 due to the tighter cap)
* Tracks SPY by ~60-75 % of the upside; cap-and-floor profile
  with the ceiling at the writing-month spot
* Premium income is higher than the 2 % OTM variant (ATM premium
  > OTM premium), partially offsetting the assigned-away P&L

## 2. Vol-of-vol spikes

Same dynamics as `covered_call_systematic` §2 — the ATM call's
mark-to-market is more volatile than the 2 % OTM call's during
spikes. Drawdown of 6-15 % from peak in spike weeks (slightly
worse than the OTM variant's 5-12 %). Recovery dynamics are
identical.

## 3. Strong cluster overlap with `covered_call_systematic`

ρ ≈ 0.95-1.00 in all regimes. The two strategies differ only by
one strike-grid multiplier (1.00 vs 1.05 on the synthetic chain).
On the BS-priced flat-IV synthetic chain, the per-cycle premium
delta between ATM and 5 %-grid-OTM is the only differentiator.

This is **not an accidental cluster** — the two ship as parametric
variants of the same trade, with different citations to anchor
their respective rules. `bxm_replication` is the index-construction
reference; `covered_call_systematic` is the practitioner-aligned
2 % OTM offset.

Cluster-detection methodology (Phase 2 master plan §6) will
surface this pair at v0.2.0; the documentation here is the
authoritative explanation.

## 4. Expected cluster correlations with Session 2F siblings

* **`covered_call_systematic`** (Commit 2): ρ ≈ 0.95-1.00 (above).
* **`cash_secured_put_systematic`** (Commit 3): ρ ≈ 0.90-0.95.
  Put-call parity: ATM-call write + long underlying ≡
  ATM-put write + cash. The PUT index uses the same Whaley
  methodology; on synthetic chains the two are near-identical.
* **`bxmp_overlay`** (Commit 5, reframed wheel): ρ ≈ 0.90-0.95.
  CBOE BXMP combines BXM call writes with PUT put writes; this
  strategy is one half of that composite.
* **`short_strangle_monthly`** (Commit 7): ρ ≈ 0.65-0.80. Same
  short-vol exposure with different leg construction.
* **`iron_condor_monthly`** (Commit 6): ρ ≈ 0.45-0.65. Capped
  vs uncapped short-vol.

## 5. Synthetic-chain substrate caveat (mild for ATM)

The ATM strike sits at the kink of the IV smile in real markets,
so the synthetic chain's flat-IV substrate is *closest to truth*
for ATM-BXM specifically (less divergence than for OTM variants).
The strategy's monthly P&L on synthetic chains will *underestimate*
the premium income by approximately 0-5 % vs. real feeds in
moderate-skew regimes — materially smaller than the 5-15 %
underestimation `covered_call_systematic` sees at the
synthetic-grid 5 % OTM strike.

Real-feed verification with full IV skew is deferred to Phase 3
with Polygon (ADR-004 stub).

## 6. Standard-benchmark-runner mode caveat

Inherited from `covered_call_systematic` §6. Standard
`BenchmarkRunner` provides only the underlying's prices column;
strategy degrades to long-equity buy-and-hold. The full BXM P&L
(Mode 1, two-leg) is exercised in `tests/test_integration.py` via
the inner `CoveredCallSystematic.make_call_leg_prices`. Session
2H benchmark-runner refactor will wire up the call-leg
construction.

## 7. OTM-expiry close approximation

Less relevant for `bxm_replication` than for OTM variants: the
ATM call has positive intrinsic on roughly half the expiry days
(when SPY closes above the writing-month spot), so the
"OTM-expiry close approximation" caveat from
`covered_call_systematic` §7 affects only ~50 % of cycles here.
For ITM-at-expiry cycles (the other ~50 %) the close fires
correctly on the expiry bar at intrinsic value.

## 8. Calendar-month-start writes vs. third-Friday writes

Same convention as `covered_call_systematic` §8 — first-trading-
day-of-month writes vs. published BXM third-Friday writes. ≤ 10 %
per year shift in premium-income profile. Documented for
transparency; not a correctness issue.

## 9. yfinance passthrough assumption (Session 2H verification)

Same assumption as `covered_call_systematic` §9. Real-data shape
verification deferred to Session 2H. Integration tests mock the
underlying feed via `_FakeUnderlying`.

## 10. Composition-wrapper transparency

`BXMReplication` is a thin composition wrapper over
`CoveredCallSystematic`. Bug fixes or behavior changes to the
parent flow through to this strategy automatically — there is
no duplicated implementation. The metadata (`name`, `paper_doi`,
`call_leg_symbol`) is independent and reflects the BXM
canonical-rule framing; the lifecycle state machine, leg pricing,
and bridge dispatch are all delegated to the parent.

If `CoveredCallSystematic`'s lifecycle algorithm changes,
`bxm_replication`'s tests must continue to pass — this is
enforced by the integration test running the full Mode 1
backtest end-to-end through `vectorbt_bridge.run`.
