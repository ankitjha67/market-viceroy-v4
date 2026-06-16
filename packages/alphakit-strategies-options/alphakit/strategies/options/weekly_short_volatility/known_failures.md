# Known failure modes — weekly_short_volatility

> Phase 2 reframe of practitioner `weekly_theta_harvest` —
> 2-leg short-vol weekly strangle write. Carr-Wu 2009
> foundational + Bondarenko 2014 primary. The strategy will
> lose money in the regimes below; uncapped weekly cadence
> means losses can compound rapidly across consecutive weeks.

## 1. Sharp directional moves through either short strike

Weekly cadence + uncapped tails = compounding losses on
sustained directional moves. A single 5 %+ weekly move through
either short strike produces an assigned-leg loss of $5 -
premium per contract. Multi-week trends compound.

Expected behaviour in similar regimes:

* Single-week losses of $5-$15 per contract on $100 underlying
* Multi-week trends produce 4-8 consecutive losing cycles
* Drawdown 15-30 % in extended-trend windows (worse than
  monthly's 12-25 % due to higher cycle frequency)

## 2. Vol-of-vol spikes (2018 February, 2020 March)

Same severity as `short_strangle_monthly` but compressed in
time — a single vol spike during the in-position week wipes
out months of accumulated weekly premium. The
2018 February "Volmageddon" was a notable failure mode for
weekly short-vol strategies in particular.

Expected drawdown of 8-18 % from peak in the spike week.

## 3. Reframe transparency (weekly_theta_harvest → weekly_short_volatility)

The Phase 2 master-plan slug `weekly_theta_harvest` is **not**
a Phase 2 strategy. The reframe is documented in
`docs/phase-2-amendments.md` 2026-05-01.

## 4. Cluster overlap with siblings

* **`short_strangle_monthly`** (Commit 7): ρ ≈ 0.65-0.85.
  Same trade at 4× cadence + tighter OTM.
* **`variance_risk_premium_synthetic`** (Commit 11):
  ρ ≈ 0.65-0.80 — same VRP exposure direction but
  variance-swap-replication mechanics vs simple short
  strangle.
* **`covered_call_systematic`** / **`cash_secured_put_systematic`**:
  ρ ≈ 0.55-0.75. Same VRP exposure direction but different
  horizon + leg construction.

## 5. Weekly-specific synthetic-chain caveats

* **Bid-ask drag amplification.** Real weekly bid-ask drag is
  2-4 % annually (vs ~0.5-1 % for monthly). Synthetic chain
  doesn't model bid-ask; backtest overstates real net P&L by
  this margin.
* **Flat IV at weekly horizon is a worse approximation.**
  Real weekly IV term-structure has steeper curves than
  monthly; the synthetic adapter's per-DTE-bucket flat-vol
  approximation misses week-of-event IV expansion.

## 6. Standard-benchmark-runner mode caveat (degenerate)

Same as siblings. Mode 2 = zero-trade backtest. Full Mode 1
P&L exercised in `tests/test_integration.py`.

## 7. OTM-expiry close approximation (×2 legs, weekly cadence)

Per-cycle close approximations apply ×52 times per year (vs
×12 for monthly). The 1-3 % per-cycle approximation translates
to a non-trivial annual cumulative bias. Documented for
transparency.

## 8. First-trading-day-of-week edge cases

The lifecycle uses `_is_first_trading_day_of_week` (ISO-week-
number transitions). On weeks with Monday holidays (e.g. MLK
Day), the first trading day is Tuesday and writes happen there
instead. This matches practitioner conventions.

## 9. yfinance passthrough assumption (Session 2H verification)

Inherited from sibling strategies.
