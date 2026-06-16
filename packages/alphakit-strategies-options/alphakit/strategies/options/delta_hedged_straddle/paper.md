# Paper — Delta-Hedged Straddle (Black-Scholes 1973 / Carr-Wu 2009)

## Citations

**Initial inspiration:** Black, F. & Scholes, M. (1973). **The
Pricing of Options and Corporate Liabilities.** *Journal of
Political Economy*, 81(3), 637-654.
[https://doi.org/10.1086/260062](https://doi.org/10.1086/260062)

The canonical Black-Scholes derivation establishes the
**delta-hedging argument**: a continuously delta-hedged option
position has zero local exposure to the underlying's spot
direction, leaving the position's P&L proportional to *gamma ×
(realized variance − implied variance)*. The delta-hedged
straddle is the canonical implementation of this argument in
continuous time.

**Primary methodology:** Carr, P. & Wu, L. (2009). **Variance
Risk Premia.** *Review of Financial Studies*, 22(3), 1311-1341.
[https://doi.org/10.1093/rfs/hhn038](https://doi.org/10.1093/rfs/hhn038)

Carr & Wu document the variance risk premium empirically by
constructing **delta-hedged option portfolios** and measuring
the average P&L. Their finding: long-vol positions
(long delta-hedged straddles) earn negative expected returns —
the variance risk premium accrues to the writers.

This strategy is the **long-vol counterparty** to the short-vol
strategies in this family. It exists for users who want the
long-vol exposure for portfolio diversification (positive
convexity, tail-risk insurance) and who are willing to pay the
VRP cost.

BibTeX entries: `blackScholes1973` (foundational) and
`carrWu2009vrp` (primary). Both registered in
`docs/papers/phase-2.bib`.

## Why two papers

Black-Scholes (1973) is the *theoretical foundation* for the
delta-hedging argument. Carr-Wu (2009) provides the *empirical
validation* and the standard methodology for the synthetic
delta-hedged-straddle backtest. The strategy *replicates*
Carr-Wu's setup; we cite Black-Scholes as the foundational
reference.

## Differentiation from siblings

* vs `gamma_scalping_daily` (Commit 10, ρ ≈ 0.85-0.95):
  Same mechanic at slightly different parameterisation. Gamma
  scalping is daily delta-hedged-straddle described from the
  practitioner perspective (Sinclair 2008); this strategy is
  the academic version (Carr-Wu 2009).
* vs `variance_risk_premium_synthetic` (Commit 11, ρ ≈ 0.70-0.85):
  Both target the VRP. VRP-synth uses Carr-Wu §2 variance-swap
  replication weights (full strike-grid weighted portfolio);
  this strategy is the simpler ATM-straddle approximation.
* vs short-vol siblings: ρ ≈ -0.7 to -0.9 (this is the LONG-vol
  side; expected P&L sign is opposite).

## Bridge integration: 2 discrete legs + dynamic-hedge underlying

Same `discrete_legs` dispatch as other multi-leg strategies, with
one new wrinkle: the underlying gets a **time-varying
`TargetPercent` weight** (the daily delta-hedge ratio). This is
the first Session 2F strategy that exercises the underlying
weight non-trivially.

* call leg + put leg: `+1` at write, `-1` at close (Amount via
  `discrete_legs`)
* underlying: `-net_delta_t` on each in-position bar (TargetPercent,
  time-varying)

### Stateful coupling (deliberate)

`make_legs_prices` stores per-cycle metadata (write date, expiry,
strike, sigma) on `self._cycles` as a side effect.
`generate_signals` reads `self._cycles` (plus the underlying spot
from `prices`) to compute per-bar net delta and emit the hedge
weight. This couples the two methods via internal state —
documented as a deliberate Phase 2 design choice for true daily
delta hedging.

The alternative (storing metadata as auxiliary columns in the
prices DataFrame) was considered and rejected because non-tradable
metadata columns disturb vectorbt's mark-to-market under
`cash_sharing=True`.

If `generate_signals` is called *without* prior `make_legs_prices`
(Mode 2: only underlying), the strategy emits all-zero weights
— degenerate no-trade. This is the standard `BenchmarkRunner`
fallback.

## Published rules (Carr-Wu 2009, monthly delta-hedged ATM straddle)

For each first trading day of a calendar month *t*:

1. **Long call.** Strike = `closest_chain_strike(spot_t)` (ATM).
2. **Long put.** Strike = same ATM strike (the straddle).
3. **Expiry.** First chain expiry > 25 days from write.
4. **Daily delta hedge.** At each in-position bar, recompute the
   straddle's net delta = `call_delta(spot, K, TTE, r, sigma) +
   put_delta(...)` and adjust the underlying position to
   `-net_delta` (offset).
5. **Close.** At expiry, close all three positions (call, put,
   underlying-hedge).

Net P&L per cycle ≈ gamma × (realized_var − implied_var) ×
notional — the model-free variance risk premium on a single
underlying. Carr-Wu document this is *negative on average* for
S&P 500 ATM straddles.

## Data Fidelity

* **Greeks are BS-computed.** The synthetic-options adapter
  exposes BS-computed deltas directly (`OptionQuote.delta`); the
  strategy uses these (or recomputes them via `bs.call_delta` /
  `bs.put_delta`) for the daily hedge ratio. No model risk
  beyond the BS-with-RV-as-IV approximation that the synthetic
  chain itself embeds.
* **Sigma frozen per cycle.** The synthetic chain prices each
  expiry-bucket at a fixed RV-derived sigma; the strategy uses
  this sigma constantly within a cycle for delta computation.
  Real markets have sigma updates per bar (vol surface evolves);
  this approximation is conservative (under-states intracycle
  delta drift).
* **No bid-ask drag.** Real delta-hedging has high turnover
  (daily underlying rebalances) which incurs significant bid-ask
  drag. Synthetic backtest doesn't model this.

Real-feed verification deferred to Phase 3 with Polygon
(ADR-004 stub).

## Expected synthetic-chain Sharpe range

**Mode 1 (full delta-hedged straddle):** `−0.3 to −0.1` per
Carr-Wu 2009 — the strategy is expected to *lose* money on
average (paying the VRP). Diversification value comes from the
positive correlation with realised vol (the strategy gains in
vol spikes when other risk assets lose).

**Mode 2 (degenerate underlying-only):** all-zero weights, no
trade.
