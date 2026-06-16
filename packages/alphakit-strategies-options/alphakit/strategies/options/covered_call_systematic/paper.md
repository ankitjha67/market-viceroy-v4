# Paper — Systematic Covered Call (Whaley 2002 / Israelov-Nielsen 2014)

## Citations

**Initial inspiration:** Whaley, R. E. (2002). **Return and risk
of CBOE Buy Write Monthly Index.** *Journal of Derivatives*, 10(2),
35-42. [https://doi.org/10.3905/jod.2002.319188](https://doi.org/10.3905/jod.2002.319188)

**Primary methodology:** Israelov, R. & Nielsen, L. N. (2014).
**Covered call strategies: One fact and eight myths.** *Financial
Analysts Journal*, 70(6), 23-31. Israelov & Nielsen decompose
covered-call returns into equity beta + short volatility + an
implicit short put (via put-call parity), confirming that the BXM-
style monthly write earns its OOS Sharpe primarily as compensation
for the variance risk premium rather than from the equity premium
alone. The 2 % OTM offset variant trades premium income for upside
participation. [https://doi.org/10.2469/faj.v70.n6.5](https://doi.org/10.2469/faj.v70.n6.5)

BibTeX entries are aggregated in `docs/papers/phase-2.bib` under
`whaley2002bxm` (foundational) and `israelovNielsen2014covered`
(primary) — both registered alongside this strategy's commit.

## Why two papers

Whaley (2002) is the seminal *index construction* paper but the
canonical BXM index uses an exactly-ATM strike rule. The strategy
here implements a parametric variant (default 2 % OTM) which is
the form Israelov & Nielsen (2014) study explicitly and which
matches retail / institutional covered-call writing conventions.
We anchor the implementation on Israelov-Nielsen because that is
the paper whose three-factor decomposition (equity + short vol +
short put) the strategy *replicates*; we cite Whaley 2002 as the
foundational reference for the deterministic monthly-write
construction whose ATM-special-case is BXM.

## Differentiation from Phase 1 `covered_call_proxy`

Phase 1's `covered_call_proxy` (volatility family, ADR-002 _proxy
suffix) is a **realized-vol overlay**: long equity scaled by
`target_vol / realized_vol` capped at `max_leverage`. It does *not*
consume an option chain — the "covered call" framing is a proxy
for vol-selling exposure derived purely from price returns.

Phase 2's `covered_call_systematic` consumes a real
`OptionChain` from the synthetic-options adapter (ADR-005, Phase 2
Session 2C). The chain provides explicit strike grid, multi-expiry
term structure, and Black-Scholes-priced quotes including greeks.
The strategy expresses its position in two columns — long
underlying + short call — rather than as a modulated equity weight.

Both slugs co-exist on main: `covered_call_proxy` stays as the
Phase 1 realized-vol-based approximation it always was;
`covered_call_systematic` is the canonical Phase 2 form.

Expected cluster correlation with the Phase 1 proxy:
ρ ≈ 0.85-0.95 in neutral-to-rising-vol regimes (both express the
same short-vol premium); lower in trending-equity regimes where
the synthetic chain's flat-IV substrate diverges from realized-vol
overlay dynamics. Documented in `known_failures.md` cluster section.

## Bridge integration: `discrete_legs` metadata

The synthetic short-call leg is **written-and-held** for ~30 days,
not continuously rebalanced. Under the default
`vectorbt SizeType.TargetPercent` semantics every existing strategy
uses, a static `weight = -1.0` on the call leg every bar would
mean "rebalance to −100 % of equity in this asset every bar,"
causing the bridge to sell ever-more contracts as the premium
decays from ~$5 → $0 across the monthly cycle and producing
runaway short P&L.

This strategy declares `discrete_legs = (call_leg_symbol,)` — an
optional `StrategyProtocol` attribute introduced for Session 2F.
The `vectorbt_bridge` reads this via
`alphakit.core.protocols.get_discrete_legs` and dispatches
`SizeType.Amount` for the declared columns,
`SizeType.TargetPercent` for the rest. Under `Amount` semantics,
the strategy's emitted weight at each bar is interpreted as
**number of shares traded this bar** — not target dollar
exposure — so a clean -1 on the write bar opens a one-contract
short position that is held through the cycle without
accumulating, and a +1 on the close bar flattens it.

See `docs/phase-2-amendments.md` 2026-05-01 entry "bridge
architecture extension for discrete-traded legs" for the full
rationale, the diagnostic evidence, and the Python-Protocol
semantics that constrained the implementation to a documented-
optional pattern (rather than declaring `discrete_legs` on the
Protocol class body).

## Published rules (Israelov & Nielsen 2014, BXM-aligned)

For each first trading day of a calendar month *t*:

1. **Strike.** ``K = closest_chain_strike(spot_t × (1 + otm_pct))``
   — default `otm_pct = 0.02`. Snap to the smallest available chain
   strike ≥ `spot × 1.02`. (The synthetic chain's 9-strike grid
   spans 0.80×–1.20× spot; the snap target lies in the chain
   reliably.)
2. **Expiry.** First chain expiry strictly later than 25 days from
   the write date — i.e. the first monthly third-Friday after the
   next month-start. Falls back to the latest available chain
   expiry only if no expiry clears the 25-day floor.
3. **Position.** Long 1 unit underlying, short 1 unit of the call
   identified by (strike, expiry). Hold through expiry; on the
   next first-trading-day-of-month, write a fresh call.
4. **Weights output.** `+1.0` underlying every bar. Call leg:
   `-1.0` on each write bar (open short via `Amount` semantics),
   `+1.0` on each close bar (flatten short before next write),
   `0.0` elsewhere.

The premium series of the synthetic short-call leg is constructed
by `CoveredCallSystematic.make_call_leg_prices(underlying_prices,
chain_feed=…)`, which:

* On each write date, calls
  `chain_feed.fetch_chain(underlying_symbol, write_date)` and
  selects the call per the rules above.
* Between write and expiry, daily-marks the call premium via
  `bs.call_price(spot_t, K, T_t, r=0.045, σ=chain_iv)`.
* At expiry, sets the leg's price to intrinsic
  (`max(0, S_T − K)`); on the bar(s) between expiry and the
  next write date the leg's price is 0 (no position held); at
  the next write date a fresh call is written and the price
  jumps to the new BS premium.

`CoveredCallSystematic.generate_signals(prices)` reads back the
write/close lifecycle by detecting zero-to-positive (write) and
positive-to-zero (close) discontinuities in the leg's price
series.

## Data Fidelity (mandatory note for all Session 2F strategies)

The Phase 2 default options feed is the **synthetic-options
adapter** (ADR-005). It produces deterministic Black-Scholes-
priced chains from realized-vol-derived implied volatility on the
underlying's price history. The adapter's documented limitations
flow through to this strategy:

* **Flat IV across strikes** (no skew). The 2 % OTM call is priced
  at the same IV as the ATM call, so the strategy captures none of
  the *skew*-component of the put-call-parity-equivalent short put
  decomposition Israelov-Nielsen describe. The BS-priced premium
  approximates the *level* of the IV but not its strike-conditional
  shape.
* **No bid-ask spread / financing model.** `bid == ask == last`.
  Real-world covered-call writes lose ~0.5-1 % per year to
  bid-ask in retail execution; this strategy's synthetic backtest
  does not reflect that drag.
* **No volume / open interest.** Liquidity-weighted strategies
  cannot test capacity faithfully.
* **Single risk-free rate.** Phase 2 uses `r = 4.5 %` as a
  constant. Phase 3 will source FRED's 3-month T-bill yield per
  as-of date.

Real-feed verification with full IV skew and bid-ask spreads is
deferred to Phase 3 with the Polygon adapter (ADR-004 stub for
Phase 2). Until then, the strategy's synthetic-chain backtest
demonstrates *signal-logic correctness* and approximates the
*level* of the BXM-style covered-call return — but the absolute
Sharpe and the OOS regime sensitivity are approximations.

## Expected synthetic-chain Sharpe range

**Mode 1 (full covered call, end-to-end through bridge with
discrete_legs dispatch):** `0.3-0.6` on the BXM-style OOS
literature (Whaley 2002 Table 2 reports 0.45 over 1988-2001;
Israelov-Nielsen 2014 Table 1 reports 0.4-0.5 across the
1986-2013 sample for ATM and 2 % OTM variants). This is the
canonical evaluation path; exercised in
`tests/test_integration.py` against a synthetic 2-column panel
constructed via `make_call_leg_prices`.

**Mode 2 (buy-and-hold approximation, standard benchmark
runner):** SPY-fixture buy-and-hold range (Sharpe 0.3-0.5 on the
Session 2D/2E synthetic fixture data). This is the path the
standard `BenchmarkRunner` exercises until Session 2H wires up
the synthetic-options call-leg construction. Reported in
`benchmark_results.json` with an explicit `note` field
documenting the mode.
