# Paper — Weekly Short Volatility (Carr-Wu 2009 / Bondarenko 2014, reframed weekly_theta_harvest)

## Reframe context

This strategy is the **academic reframe** of the practitioner
`weekly_theta_harvest` slug — see
[`docs/phase-2-amendments.md`](../../../../../../docs/phase-2-amendments.md)
2026-05-01 entry "reframe weekly_theta_harvest →
weekly_short_volatility". "Theta harvesting" is practitioner
terminology with no peer-reviewed academic anchor. The economic
content is **short volatility on a weekly horizon** — the strategy
collects the variance risk premium over 7-day cycles.

## Citations

**Initial inspiration:** Carr, P. & Wu, L. (2009). **Variance
risk premia.** *Review of Financial Studies*, 22(3), 1311-1341.
[https://doi.org/10.1093/rfs/hhn038](https://doi.org/10.1093/rfs/hhn038)

Carr & Wu document the variance risk premium across horizons —
both monthly and weekly — using model-free variance-swap
replication. Their finding that the VRP is robust to horizon
choice is the empirical foundation for short-vol-at-weekly-horizon
strategies.

**Primary methodology:** Bondarenko, O. (2014). **Why are put
options so expensive?** *Quarterly Journal of Finance*, 4(1),
1450015.
[https://doi.org/10.1142/S2010139214500050](https://doi.org/10.1142/S2010139214500050)

Bondarenko's empirical setup includes both monthly and weekly
horizon tests. The weekly OTM put/call write is the canonical
short-vol-at-weekly-horizon trade: premia are smaller per cycle
(~$0.50–$1.00 vs monthly's $1–$5) but cycles are 4× more
frequent so cumulative annual premium is similar; the trade-off
is position-management overhead.

BibTeX entries: `carrWu2009vrp` (foundational) and
`bondarenko2014puts` (primary).

## Why two papers

Carr-Wu (2009) provides the *theoretical* and *empirical*
foundation for the VRP across horizons. Bondarenko (2014)
provides the *strike-conditional* analysis (put-skew dominance)
and the operational details for OTM writes. The strategy
*replicates* Bondarenko's weekly setup; we cite Carr-Wu as the
foundational reference.

## Differentiation from `weekly_theta_harvest` folklore

| Aspect | `weekly_theta_harvest` (dropped) | `weekly_short_volatility` (this strategy) |
|---|---|---|
| Framing | "Harvest theta" practitioner term | Variance-risk-premium harvest |
| Citation | Folklore | Carr-Wu 2009 + Bondarenko 2014 |
| Phase 2 status | Reframed | Shipped |

The reframe preserves the *economic content* (collect short-vol
premium on weekly cycles) while replacing the practitioner
terminology with the academic framing.

## Differentiation from siblings

* vs `short_strangle_monthly` (Commit 7, ρ ≈ 0.65-0.85): Same
  trade structure (short OTM put + short OTM call) but weekly
  cadence and tighter OTM (5 % vs 10 %).
* vs `variance_risk_premium_synthetic` (Commit 11): VRP-synth
  uses straddle replication per Carr-Wu §2 (theoretically
  cleaner); weekly_short_volatility is the simpler
  short-strangle-at-weekly-horizon variant.
* vs `covered_call_systematic` / `cash_secured_put_systematic`
  (ρ ≈ 0.55-0.75): Same VRP exposure direction but different
  horizon and 2-leg vs 1-leg construction.

## Bridge integration

Same 2-leg `discrete_legs` dispatch as
`short_strangle_monthly`. The strategy declares
`discrete_legs = (put_leg_symbol, call_leg_symbol)`; bridge
applies `Amount` semantics to both option legs and
`TargetPercent` (default) to the underlying — but the strangle
emits `0.0` weight on the underlying.

Cross-reference: `docs/phase-2-amendments.md` 2026-05-01 "bridge
architecture extension for discrete-traded legs".

## Published rules (Bondarenko 2014, weekly horizon)

For each first trading day of a calendar week *w*:

1. **Short put leg.** Strike = `closest_chain_strike(spot_w × 0.95)`
   — 5 % OTM. (Tighter than the 10 % OTM monthly default because
   weekly options have less time value at deeper OTMs.)
2. **Short call leg.** Strike = `closest_chain_strike(spot_w × 1.05)`
   — 5 % OTM.
3. **Expiry.** First chain expiry strictly later than 3 days
   from the write date — i.e. the next weekly Friday after a
   Monday write. Falls back to the latest available chain
   expiry only if no expiry clears the 3-day floor.
4. **Position.** Both short legs simultaneously, no underlying
   long. Hold through expiry; on the next first-trading-day-of-
   week, write a fresh weekly strangle.
5. **Weights output.** `0.0` underlying every bar (pure-options
   trade). Put + call legs: `-1.0` on write bars, `+1.0` on
   close bars (Amount via `discrete_legs`).

The synthetic chain's expiry grid includes 4 weekly Fridays
(`alphakit.data.options.synthetic._weekly_fridays`); a Monday
write with 3-day-DTE floor naturally selects the next Friday's
expiry (typically 4 days away).

## Data Fidelity

Same caveats as monthly siblings, with weekly-specific
considerations:

* **Weekly cadence amplifies turnover.** Annualised turnover is
  ~52 cycles vs 12 for monthly siblings. Real bid-ask drag
  scales linearly with turnover; the synthetic chain doesn't
  model bid-ask, so the strategy's synthetic backtest
  overstates real net P&L by 2-4 % annually for weekly cadence
  (vs <1 % for monthly).
* **Flat IV at weekly horizon.** Real weekly IV term-structure
  has a steeper curve than monthly (week-of-event IV expansion
  is more pronounced); the synthetic chain's flat-vol-per-DTE-
  bucket approximation is less faithful at the weekly horizon
  than at monthly.

## Expected synthetic-chain Sharpe range

**Mode 1 (full weekly strangle):** `0.4-0.7` per Bondarenko
2014 weekly setup — similar Sharpe magnitude to monthly
strangles, with different drawdown timing (weekly cycles
produce more frequent but smaller per-cycle losses).

**Mode 2 (degenerate underlying-only):** all-zero weights, no
trade.
