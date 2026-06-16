# Paper — Put Skew Premium (Bakshi-Kapadia-Madan 2003 / Garleanu-Pedersen-Poteshman 2009)

## ⚠ Critical substrate caveat (read first)

The **synthetic-options chain has flat implied volatility across
strikes by construction** (ADR-005, see
`docs/feeds/synthetic-options.md`). The economic content of this
strategy — the **put-skew premium** — is *systematically zero* on
the synthetic substrate because the OTM put and OTM call are
priced with the same IV.

**The synthetic backtest of this strategy is uninformative for
its target premium.** It validates the *signal-logic correctness*
(strategy emits the right weights at the right bars; lifecycle
detection works; bridge integration works) but cannot evaluate
the strategy's expected return.

The strategy ships in Phase 2 as a faithful implementation of the
published methodology with documented Phase 3 verification path
against real options chains via Polygon (ADR-004 stub).

This caveat is repeated in `known_failures.md` §1 and in the
`benchmark_results.json` `note` field.

## Citations

**Initial inspiration:** Bakshi, G., Kapadia, N. & Madan, D.
(2003). **Stock Return Characteristics, Skew Laws, and the
Differential Pricing of Individual Equity Options.** *Review of
Financial Studies*, 16(1), 101-143.
[https://doi.org/10.1093/rfs/16.1.0101](https://doi.org/10.1093/rfs/16.1.0101)

Bakshi-Kapadia-Madan derive the model-free risk-neutral skew
formula and document the put-skew premium on individual equities
and indices: real OTM puts trade systematically richer (higher
IV) than real OTM calls at the same |delta|, reflecting left-tail
demand for portfolio protection.

**Primary methodology:** Garleanu, N., Pedersen, L. H. &
Poteshman, A. M. (2009). **Demand-Based Option Pricing.**
*Review of Financial Studies*, 22(10), 4259-4299.
[https://doi.org/10.1093/rfs/hhp005](https://doi.org/10.1093/rfs/hhp005)

Garleanu-Pedersen-Poteshman provide the *demand-based*
microfoundation: end-user demand for portfolio insurance pushes
OTM-put prices above their no-arbitrage levels, leaving a
systematic short-skew premium for sellers. The risk-reversal
trade (short OTM put + long OTM call) is the canonical isolated
capture of this premium.

BibTeX entries: `bakshiKapadiaMadan2003` (foundational) and
`garleanuPedersenPoteshman2009` (primary).

## Strategy structure

For each first trading day of a calendar month:

1. **Short OTM put.** Strike = `closest_chain_strike(spot ×
   0.95)` (default 5 % OTM).
2. **Long OTM call.** Strike = `closest_chain_strike(spot ×
   1.05)` (default 5 % OTM).
3. **Expiry.** First chain expiry > 25 days from write.
4. **Position sizing.** -1 short put + +1 long call per cycle.
   Net premium received = put_premium - call_premium (positive
   on real chains where put-skew makes the put more expensive;
   approximately zero on the synthetic chain due to flat IV).
5. **Close.** Both legs close at expiry, each at intrinsic.

## Differentiation from siblings

* vs `short_strangle_monthly` (Commit 7): Both are 2-leg trades.
  Strangle is short BOTH legs (vol harvest, no directional bias);
  this is short put + LONG call (directional bullish bias).
* vs `cash_secured_put_systematic` (Commit 3): Both are short
  OTM put. CSP holds the underlying long (cash collateral); this
  uses a long call to hedge instead. Different hedge form.
* vs `skew_reversal` (Commit 14): Same skew-premium target with
  symmetric (short put + long call) construction. The two ship
  as variants — `put_skew_premium` is the unconditional
  systematic write; `skew_reversal` is conditional on a
  skew-magnitude threshold.

Cluster: ρ ≈ 0.30-0.50 with directional siblings (covered call,
CSP); higher ρ with `skew_reversal` (~0.85-0.95 in regimes where
both fire). The substrate caveat means synthetic-chain ρ
estimates are NOT representative of real-feed ρ.

## Bridge integration

2 discrete legs: short put (-1 at write / +1 at close) + long
call (+1 at write / -1 at close). Underlying weight 0.

## Data Fidelity

**Critical:** synthetic chain has flat IV, so the put-skew
premium is structurally zero. This is the single dominant
limitation of this strategy's synthetic backtest. ALL other
substrate caveats (no bid-ask, no volume / OI, single risk-free
rate) apply on top.

Real-feed verification with actual put-skew is **mandatory**
for any meaningful evaluation of this strategy. Phase 3 path:

1. Polygon real-chain integration (ADR-004 → active).
2. Re-run benchmark with real OTM put and call IVs.
3. Confirm put-leg IV > call-leg IV consistently (the skew).
4. Quantify the systematic short-skew premium per cycle.

Until then, the synthetic-chain backtest is a **smoke test for
strategy plumbing**, not a P&L estimate.

## Expected synthetic-chain Sharpe range

**Mode 1 (synthetic chain, flat IV):** approximately ±0.0
— the strategy collapses to a directional long-call P&L plus
statistical noise. Any non-zero Sharpe on the synthetic
backtest is a function of the underlying's drift through the
strikes, NOT the put-skew premium.

**Mode 1 (real chain, put-skew present):** estimated 0.5-0.8
based on Garleanu-Pedersen-Poteshman §V — but THIS IS NOT
WHAT THE SYNTHETIC BACKTEST WILL PRODUCE. Real-feed
verification required.

**Mode 2 (degenerate underlying-only):** all-zero weights.
