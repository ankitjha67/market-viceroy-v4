# Known failure modes — skew_reversal

## ⚠ 1. Substrate caveat (LOAD-BEARING)

**The synthetic-options chain has flat IV across strikes (ADR-005).
The put-skew z-score this strategy monitors is structurally zero;
the trigger never fires; the synthetic backtest is a degenerate
no-trade case.** Final equity = initial cash exactly, zero
returns, zero Sharpe.

Strategy ships as faithful methodology implementation for Phase 3
real-feed verification (Polygon, ADR-004 stub). The synthetic
backtest validates plumbing (StrategyProtocol conformance,
bridge dispatch wiring) but cannot evaluate the strategy's
expected return.

This caveat is the load-bearing limitation. All other failure
modes documented below would only become observable on real
chains.

## 2. Real-chain expected behaviour (Phase 3)

When run on real chains where put-skew exists:

* Trigger fires ~5-10 % of months under typical regimes
  (skew z-score > 1.5σ).
* When triggered, short OTM put earns elevated premium
  (Garleanu-Pedersen-Poteshman §V documents the magnitude).
* Tail-risk regime: short-put assignment in stress events
  (2008 Q4, 2020 March) — the trigger fired into the
  pre-stress vol bump, then realized vol exceeded implied.

## 3. Conditional vs unconditional comparison

* `put_skew_premium` (Commit 13): unconditional, trades every
  cycle, captures average put-skew premium.
* `skew_reversal` (this strategy): conditional, trades only
  when skew is unusually elevated — captures the
  mean-reversion of skew toward its long-run level.

Real-feed empirical comparison (Phase 3 deliverable): which
variant has higher Sharpe? Garleanu-Pedersen-Poteshman §V
suggests the conditional variant has higher Sharpe per trade
but lower trade frequency. Net annualised Sharpe is
approximately equal (~0.4-0.6).

## 4. Cluster overlap

Real-feed (Phase 3):
* `put_skew_premium`: ρ ≈ 0.85-0.95 in regimes where both
  fire; lower elsewhere.
* `cash_secured_put_systematic`: ρ ≈ 0.40-0.60 (overlap on
  short-put leg).

Synthetic-chain: all clusters are zero-correlated since this
strategy emits zero weights.

## 5. Standard-benchmark-runner mode caveat

Trivially degenerate — same as siblings. All-zero weights
on Mode 2 (underlying only).

## 6. yfinance passthrough assumption (Session 2H verification)

Inherited from sibling strategies.

## 7. No price discontinuity / lifecycle test possible

Because the synthetic backtest never opens a position, there
are no zero-to-positive or positive-to-zero discontinuities
in the leg's price series. The lifecycle-detection helper
returns empty masks. This is *expected behaviour* for this
substrate, not a bug.
