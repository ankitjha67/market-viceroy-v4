# Paper — BXM Replication (Whaley 2002, sole anchor)

## Citation

**Whaley, R. E. (2002).** *Return and Risk of CBOE Buy Write
Monthly Index*. Journal of Derivatives, 10(2), 35-42.
[https://doi.org/10.3905/jod.2002.319188](https://doi.org/10.3905/jod.2002.319188)

The CBOE BXM index is a passive benchmark of the *exactly-ATM*
monthly covered-call write: long the S&P 500 cash index, short a
1-month at-the-money S&P 500 call written each third Friday and
held to expiry. Whaley constructs the index, documents the rule,
and reports OOS performance through 2001 (Sharpe ≈ 0.45).

This strategy *replicates* the canonical BXM construction —
single anchor, no parametric variation — distinguishing it from
``covered_call_systematic`` which ships the practitioner-aligned
2 % OTM offset variant studied in Israelov-Nielsen 2014.

BibTeX entry: `whaley2002bxm` in `docs/papers/phase-2.bib`
(registered alongside the ``covered_call_systematic`` commit and
reused here as sole anchor).

## Differentiation from `covered_call_systematic`

| Aspect | `covered_call_systematic` | `bxm_replication` |
|---|---|---|
| Strike | smallest grid strike ≥ `spot × 1.02` (≈ 5 % OTM on synthetic 5 %-grid) | `spot × 1.00` (exactly ATM, exact grid match) |
| Citation | Whaley 2002 + Israelov-Nielsen 2014 | Whaley 2002 sole |
| Implementation | Parametric `otm_pct ∈ (0, 0.50]` | `otm_pct = 0.0` fixed via composition |
| Cluster ρ vs sibling | — | ≈ 0.95-1.00 |

Both ship as canonical Phase 2 forms. ``bxm_replication`` is the
*reference* benchmark (literally the published index methodology);
``covered_call_systematic`` is the *parametric* variant that
matches retail / institutional covered-call writing conventions.

## Bridge integration

`bxm_replication` inherits the `discrete_legs` dispatch via the
composition wrapper over ``CoveredCallSystematic``. The
`vectorbt_bridge` reads
``get_discrete_legs(BXMReplication())`` →
``("SPY_CALL_OTM00PCT_M1",)`` and dispatches `SizeType.Amount`
for the leg per the Session 2F bridge architecture extension.

Cross-reference: `covered_call_systematic/paper.md` Bridge
Integration section + `docs/phase-2-amendments.md` 2026-05-01
"bridge architecture extension for discrete-traded legs".

## Published rules (Whaley 2002 BXM methodology)

For each first trading day of a calendar month *t*:

1. **Strike.** ``K = spot_t`` exactly. Snap to the closest
   available chain strike that meets ``K ≥ spot``; on the
   synthetic 9-strike grid the 1.00 multiplier matches exactly
   so the snap is trivial.
2. **Expiry.** First chain expiry strictly later than 25 days
   from the write date. (The published BXM uses the third Friday
   of the calendar-following month — see calendar caveat in
   `known_failures.md`.)
3. **Position.** Long 1 unit underlying, short 1 unit ATM call.
   Hold through expiry; on the next first-trading-day-of-month,
   write a fresh ATM call.
4. **Weights output.** Inherited from `CoveredCallSystematic`:
   `+1.0` underlying every bar (TargetPercent), call leg `-1.0`
   on writes / `+1.0` on closes / `0.0` elsewhere (Amount via
   `discrete_legs`).

## Data Fidelity (mandatory note for all Session 2F strategies)

Same substrate caveats as `covered_call_systematic`: synthetic
chain has flat IV across strikes (no skew), no bid-ask spread,
no volume / open interest, single risk-free rate. For ATM-BXM
specifically, the flat-IV substrate is *less* of an approximation
than for OTM variants because the ATM strike sits at the kink of
the IV smile in real markets — the BS-with-realized-vol
approximation is closest to truth here. Real-feed verification
remains Phase 3 with Polygon (ADR-004 stub).

## Expected synthetic-chain Sharpe range

`0.4-0.6` matching the published BXM OOS literature (Whaley 2002
Table 2 reports 0.45 over 1988-2001; subsequent CBOE reports
through 2018 confirm 0.4-0.5 per Israelov-Nielsen 2014 Table 1
for the ATM variant).

The standard `BenchmarkRunner` exercises Mode 2 (buy-and-hold
approximation) until Session 2H wires up the call-leg
construction; the full Mode 1 BXM P&L is exercised in
`tests/test_integration.py`.
