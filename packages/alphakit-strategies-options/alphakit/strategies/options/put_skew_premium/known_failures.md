# Known failure modes — put_skew_premium

## ⚠ 1. Substrate caveat (LOAD-BEARING)

**The synthetic-options chain has flat implied volatility across
strikes by construction (ADR-005). This strategy's economic
content (put-skew premium harvesting) cannot be properly tested
on this substrate.** The signal will execute (legs trade,
lifecycle is correct) but the *premium it targets is
systematically zero on the synthetic chain* because the OTM put
and OTM call are priced with the same IV.

The strategy ships in Phase 2 as a faithful implementation of
the published methodology (Bakshi-Kapadia-Madan 2003 +
Garleanu-Pedersen-Poteshman 2009) with documented Phase 3
verification path against real options chains via Polygon.

**Treat the synthetic-chain Sharpe number as uninformative** —
it is a smoke test for strategy plumbing, not a P&L estimate.
Real-feed verification is mandatory for any meaningful
evaluation.

This caveat is repeated in `paper.md` and in the
`benchmark_results.json` `note` field.

## 2. Real-chain expected behaviour (Phase 3 verification)

When run on real options chains with put-skew present:

* Net premium received per cycle = put_premium - call_premium.
  Real markets: put_premium > call_premium for matched OTM
  offsets (real put-skew). Synthetic: put_premium ≈ call_premium.
* Per-cycle P&L on real chains:
  + Net positive premium received at write (~0.5-1.5 % of
    underlying)
  + Loss capped at intrinsic-call-payoff (uncapped on the
    upside, since long call protects)
  + Loss uncapped on the downside (short put assigned)

## 3. Tail-risk regimes

When the underlying drops sharply through the put strike, the
short-put leg is assigned at material loss. The long-call leg
expires worthless (no offset). Risk-reversal is **directionally
long underlying** in P&L sign.

Expected drawdown in stress:
* Single-cycle losses of 5-10 % of underlying notional during
  10 %+ monthly drops.
* Multi-month tail events (2008 Q4, 2020 March) compound losses
  rapidly.

## 4. Cluster overlap

* **`skew_reversal`** (Commit 14): ρ ≈ 0.85-0.95 (in regimes
  where both fire). Same target premium with conditional vs
  unconditional firing.
* **`covered_call_systematic`** / **`cash_secured_put_systematic`**:
  ρ ≈ 0.30-0.55 — different leg structures.
* **`bxmp_overlay`** (Commit 5): ρ ≈ 0.40-0.60.
* **`short_strangle_monthly`** / **`variance_risk_premium_synthetic`**:
  ρ ≈ 0.50-0.70 (overlap on short-put leg).

The substrate caveat means synthetic-chain ρ estimates are NOT
representative of real-feed ρ.

## 5. Standard-benchmark-runner mode caveat (degenerate)

Same as siblings.

## 6. OTM-expiry close approximation

Same as siblings. ×2 legs.

## 7. Calendar-month-start writes vs. third-Friday writes

Same convention as siblings.

## 8. yfinance passthrough assumption (Session 2H verification)

Inherited from sibling strategies.
