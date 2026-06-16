# Paper — Calendar Spread ATM (Goyal-Saretto 2009)

## Citation

**Goyal, A. & Saretto, A. (2009). Cross-Section of Option Returns
and Volatility.** *Journal of Finance*, 64(4), 1857-1898.
[https://doi.org/10.1111/j.1540-6261.2009.01493.x](https://doi.org/10.1111/j.1540-6261.2009.01493.x)

Goyal-Saretto study cross-sectional option returns conditional
on the *implied-vs-realized vol gap* and the *term structure of
implied volatility*. Their analysis frames the calendar spread
as a term-structure-normalisation trade: when the front-month IV
is elevated relative to back-month (event-driven, near-expiry
vol bumps), the spread profits as front-month theta decays
faster.

The strategy *replicates* Goyal-Saretto's calendar-spread setup
on synthetic chains: short front-month ATM call + long
back-month ATM call, both closed at the front-month expiry.

BibTeX entry: `goyalSaretto2009` in `docs/papers/phase-2.bib`.

## Strategy structure

For each first trading day of a calendar month *t*:

1. **Short front-month ATM call.** Strike = closest grid strike
   to spot at write. Expiry = first chain expiry > 25 days
   from write (~30-day DTE).
2. **Long back-month ATM call.** Same ATM strike, longer
   expiry = first chain expiry > 55 days from write (~60-day
   DTE). The back leg uses the SAME strike as the front
   (same-K calendar — pure term-structure exposure, no skew
   exposure).
3. **Close.** Both legs close at front-month expiry. Front
   closes at intrinsic (`max(0, S_T − K)`); back closes at
   its remaining time value (BS-priced with back-sigma at
   ~30 days residual TTE).
4. **Sizing.** -1 contract front + +1 contract back per cycle.

Net P&L per cycle = (back_value_at_close + front_premium_at_write)
− (back_premium_at_write + front_intrinsic_at_close). Profits
when realized vol at front expiry < implied vol at write
(theta-decay harvest) and when back-month IV is sustained
through to the front expiry.

## Term-structure dependence on synthetic chains

The synthetic-options adapter (ADR-005) maps DTE buckets to
realized-vol windows:

* `< 45 DTE` → 30-day RV (front-month bucket)
* `< 120 DTE` → 60-day RV (back-month bucket)
* `≥ 120 DTE` → 90-day RV

The front-month (~30 DTE) and back-month (~60 DTE) calls are
priced with *different sigmas* (rv30 vs rv60), giving a
meaningful synthetic term structure — though typically mild
(rv30 and rv60 differ by 1-3 vol points on stable underlyings).

Real markets have richer term-structure variation (event-driven
front-month IV bumps, seasonal effects). The synthetic substrate
captures the *direction* of the trade but not its full magnitude.

## Differentiation from siblings

* vs `covered_call_systematic` (Commit 2): Single-leg vs 2-leg
  term-structure spread. ρ ≈ 0.30-0.50 — different exposures.
* vs `bxm_replication` (Commit 4): ρ ≈ 0.40-0.55. Both involve
  short ATM calls; calendar spread hedges with the long
  back-month leg.
* vs `delta_hedged_straddle` (Commit 9): ρ ≈ 0.35-0.55. Both
  target volatility but differently — calendar is term-structure
  arbitrage, delta-hedged-straddle is daily-vol harvest.

Calendar spread has the *most distinct exposure* in the family
because of its term-structure focus — none of the other Session
2F strategies span multiple expiries simultaneously.

## Bridge integration: 2 discrete legs

Standard pattern. ``discrete_legs = (front_leg_symbol,
back_leg_symbol)``; bridge applies ``Amount`` to both. Front
leg: -1 at write / +1 at close (short). Back leg: +1 at write
/ -1 at close (long). Underlying weight 0 (pure-options trade).

## Data Fidelity

* **Synthetic term structure is mild.** Rv30 vs rv60 difference
  is typically 1-3 vol points on stable underlyings; real
  markets have event-driven front-month vol spikes that
  amplify calendar-spread P&L significantly.
* **Same-K calendar (no skew exposure).** This implementation
  uses the SAME strike for both legs, isolating term-structure
  exposure. Skew-exposed calendar variants (different strikes)
  are out of scope for Phase 2.
* **Standard substrate caveats** (no bid-ask, single risk-free
  rate, etc.) apply.

Real-feed verification with realistic term-structure variation
deferred to Phase 3 with Polygon (ADR-004 stub).

## Expected synthetic-chain Sharpe range

**Mode 1 (full calendar spread):** `0.2-0.5` per Goyal-Saretto
literature. Lower magnitude than VRP-harvest strategies because
term-structure normalisation is a smaller premium than the
short-vol VRP. The synthetic-chain backtest's mild term
structure further compresses the return.

**Mode 2 (degenerate underlying-only):** all-zero weights.
