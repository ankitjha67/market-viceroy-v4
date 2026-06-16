# Paper — Gamma Scalping Daily (Hull-White 1987 / Sinclair 2008)

## Citations

**Initial inspiration:** Hull, J. C. & White, A. (1987). **The
Pricing of Options on Assets with Stochastic Volatilities.**
*Journal of Finance*, 42(2), 281-300.
[https://doi.org/10.1111/j.1540-6261.1987.tb02568.x](https://doi.org/10.1111/j.1540-6261.1987.tb02568.x)

Hull-White generalise the Black-Scholes delta-hedging argument
to stochastic-volatility regimes and document the gamma-scalping
P&L decomposition: a daily delta-hedged long-vol position earns
*gamma × (realized variance − implied variance)* per day, plus a
small higher-order vega-of-vol term. The paper provides the
theoretical foundation for the daily-rebalance trading mechanic.

**Primary methodology:** Sinclair, E. (2008). *Volatility
Trading*. John Wiley & Sons. ISBN 978-0470181998.

Sinclair's practitioner reference for systematic vol trading
documents the exact daily-gamma-scalping mechanic: long ATM
straddle, hedge delta to zero each session, capture realized
volatility relative to implied. Sinclair Chapter 7 covers the
implementation in operational detail.

BibTeX entries: `hullWhite1987svol` (foundational) and
`sinclair2008` (primary, book).

## Why two anchors

Hull-White (1987) is the *theoretical* paper documenting the
gamma-scalping P&L decomposition under stochastic vol. Sinclair
(2008) is the *practitioner manual* that operationalises the
trade. The strategy *replicates* Sinclair's setup; we cite
Hull-White as the foundational theoretical reference.

## Differentiation from `delta_hedged_straddle` (Commit 9)

Same underlying mechanic, different citation framing:

| Aspect | `delta_hedged_straddle` | `gamma_scalping_daily` |
|---|---|---|
| Anchor type | Academic | Practitioner |
| Foundational | Black-Scholes 1973 | Hull-White 1987 |
| Primary | Carr-Wu 2009 | Sinclair 2008 |
| Implementation | Self-contained | Composition wrapper |
| Cluster ρ | — | ≈ 0.95-1.00 with sibling |

Both ship as parametric variants. `delta_hedged_straddle` is
the academic-VRP-measurement framing (Carr-Wu 2009);
`gamma_scalping_daily` is the practitioner-trading framing
(Sinclair 2008). Identical trade mechanic, different citations.

## Bridge integration: 2 discrete legs + dynamic-hedge underlying

Inherited from `DeltaHedgedStraddle` via composition. See that
strategy's `paper.md` Bridge Integration section for the full
explanation.

Cross-reference: `docs/phase-2-amendments.md` 2026-05-01 "bridge
architecture extension for discrete-traded legs".

## Published rules (Sinclair 2008 daily-gamma-scalping setup)

Identical to `delta_hedged_straddle`:

1. Long ATM call + long ATM put (straddle).
2. Daily delta hedge via `-net_delta` underlying weight.
3. Monthly write/expiry cycle on synthetic chains.
4. Per-cycle metadata stored on the inner instance for the
   per-bar delta computation.

## Data Fidelity

Same caveats as `delta_hedged_straddle`. The synthetic chain's
flat-IV substrate is closest to truth at the ATM strike used by
this strategy. Real-feed verification deferred to Phase 3
(ADR-004 stub).

## Expected synthetic-chain Sharpe range

Same as `delta_hedged_straddle`: `−0.3 to −0.1` (long-vol VRP
counterparty, expected negative return per Carr-Wu / Sinclair).

The Phase 2 master plan §6 cluster-detection methodology will
flag this strategy as a near-duplicate of `delta_hedged_straddle`;
the documentation here is the authoritative explanation of the
deliberate parametric-variant framing.
