# Known failure modes — calendar_spread_atm

> Phase 2 ATM calendar spread (short front-month + long
> back-month). Goyal-Saretto 2009 sole anchor. The strategy
> will lose money in the regimes below; the front+back
> structure has asymmetric tail behaviour vs single-expiry
> short-vol siblings.

## 1. Vol crashes (RV >> IV at front expiry)

When realized vol over the front-month cycle dramatically
exceeds the back-month IV at write, the front leg's intrinsic
gain (when assigned) overwhelms the back leg's mark-to-market
gain. Net P&L is negative.

This is the canonical "wrong-way IV-bet" failure — the
strategy implicitly bets that front-month IV is too high
relative to back; if that bet is wrong, both legs move
unfavourably.

## 2. Term-structure inversion (back IV crashes faster than front)

Real markets occasionally see post-event IV crashes where the
back-month IV drops faster than the front (the event removes
uncertainty in the longer term faster than near-term). The
strategy's long-back position loses mark-to-market, partially
offsetting the front-leg theta decay.

The synthetic chain doesn't model these inversions cleanly
(per-DTE-bucket RV mapping is monotone in DTE), so this
failure mode is *under-represented* in the synthetic backtest.

## 3. Cluster overlap with siblings

Calendar spread has the **most distinct exposure** in the
family. ρ ≈ 0.30-0.55 with most siblings — term-structure
exposure is unique among Session 2F strategies.

* vs `covered_call_systematic` (Commit 2): ρ ≈ 0.30-0.50
* vs `bxm_replication` (Commit 4): ρ ≈ 0.40-0.55 (both touch
  ATM short call)
* vs `delta_hedged_straddle` (Commit 9): ρ ≈ 0.35-0.55
* vs `variance_risk_premium_synthetic` (Commit 11): ρ ≈ 0.30-0.50

## 4. Synthetic-chain term-structure caveat

The synthetic-options adapter's per-DTE-bucket sigma mapping
gives a mild term structure (rv30 and rv60 typically within
1-3 vol points). This *under-states* the calendar-spread
return relative to real markets which have:

* Event-driven front-month vol spikes (3-10+ vol points)
* Seasonal term-structure variation
* Vol smile-in-time effects (front month often has more skew)

The synthetic-chain Sharpe estimate is conservative
(lower-bound) for this strategy. Real-feed verification (Phase
3) should produce higher Sharpe magnitude.

## 5. Standard-benchmark-runner mode caveat (degenerate)

Same as other multi-leg strategies. Mode 2 (underlying-only) =
no-trade backtest, final equity = initial cash.

## 6. Same-K calendar restriction

This implementation uses the SAME strike for both legs,
isolating pure term-structure exposure. Diagonal calendar
spreads (different strikes for front and back) are NOT
supported in this strategy — see the dropped `diagonal_spread`
strategy in `docs/phase-2-amendments.md` 2026-05-01 for
rationale (no peer-reviewed citation for systematic
diagonal-spread rule).

## 7. yfinance passthrough assumption (Session 2H verification)

Inherited from sibling strategies.

## 8. OTM-expiry close approximation

Front leg closes at intrinsic on the front expiry; if the
underlying ends OTM, the close fires one bar early at small
residual time value (per the standard
`_detect_lifecycle_events` behaviour). Back leg's "close" is
its mark-to-market BS-price at that bar — typically positive
since back has ~30 days residual TTE.

## 9. Calendar-month-start writes vs. third-Friday writes

Same convention as siblings.
