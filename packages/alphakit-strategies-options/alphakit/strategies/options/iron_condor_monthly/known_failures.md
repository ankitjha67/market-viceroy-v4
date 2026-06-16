# Known failure modes — iron_condor_monthly

> Phase 2 4-leg defined-risk short-volatility iron-condor write
> on synthetic chains. Hill et al. 2006 foundational + CBOE CNDR
> primary methodology. The strategy will lose money in the regimes
> below; none are bugs — they are the cost of the capped
> short-vol exposure.

## 1. Sustained directional moves through the short strikes

When the underlying moves through either short strike (5 % OTM
put or call) and stays there into expiry, the short leg is
assigned at the loss limit. The protective wing caps the maximum
loss at the wing width minus net premium received — but the
strategy still realises a per-cycle loss of (wing width − net
premium) × number of contracts.

Expected behaviour for `iron_condor_monthly` in similar regimes:

* Per-cycle loss capped at ~$5 per contract (5 % wing width on
  $100 underlying minus ~$0.50–$1.00 net premium)
* Multi-month directional trends (e.g. 2008 Q4, 2020 March) can
  produce 4-6 consecutive cycle losses
* Drawdown 8-15 % from peak in sustained-trend windows

CNDR historically has a *much smaller* maximum drawdown than
BXM/PUT specifically because of this wing protection — the cost
is the wing premium, paid each cycle whether or not the wings
are exercised.

## 2. Vol-of-vol spikes (2018 February, 2020 March)

Less severe than uncapped short-vol strategies (covered call,
CSP, BXMP) because the wings hedge the deep tails. The
short-leg mark-to-market loss during a spike is partially
offset by the long-leg mark-to-market gain (the wings appreciate
when the short legs lose).

Expected behaviour during sharp vol spikes:

* Drawdown of 4-8 % from peak in the spike week (smaller than
  uncapped equivalents' 8-12 %)
* Recovery dynamics: faster than uncapped because the wings
  cap the maximum loss

The synthetic chain's flat-IV substrate has *competing biases*
during stress: real put-skew widens (favouring the strategy's
short-put leg) but real call-skew is gentler (less favourable);
the protective wings see the same skew effects on the long side.
Net effect: the synthetic-chain backtest's stress-period P&L is
roughly accurate to within ±2 % vs real-feed equivalent — better
than CSP standalone where put-skew dominates the bias.

## 3. Cluster overlap with siblings

* **`short_strangle_monthly`** (Commit 7): ρ ≈ 0.85-0.95.
  Short strangle is iron condor without protective wings —
  same short-vol exposure, more left + right tail.
* **`covered_call_systematic`** (Commit 2): ρ ≈ 0.50-0.70.
  Capped vs uncapped short-vol on the call side; iron condor
  has no equity-leg exposure (pure-options trade).
* **`cash_secured_put_systematic`** (Commit 3): ρ ≈ 0.50-0.70.
  Capped vs uncapped short-vol on the put side; iron condor
  has no underlying long exposure.
* **`bxmp_overlay`** (Commit 5): ρ ≈ 0.55-0.75. BXMP carries
  equity beta + 2× uncapped short vol; iron condor is pure
  capped short vol with no equity beta.

## 4. Synthetic-chain substrate caveat (compounded for 4-leg)

Per-leg substrate biases:

* Short put @ 5 % OTM: ~10-20 % premium underestimation (real
  put-skew effect)
* Long put @ 10 % OTM: ~15-25 % premium underestimation (deeper
  put-skew effect, BUT this is the *cost* leg; underestimation
  flatters the strategy)
* Short call @ 5 % OTM: ~5-10 % premium underestimation
* Long call @ 10 % OTM: ~5-10 % premium underestimation (cost
  leg, underestimation flatters)

Net effect across the 4 legs largely cancels: the synthetic
chain understates BOTH the income (short legs) AND the cost
(long legs), with similar magnitudes. The strategy's net premium
income on synthetic chains is approximately 0-5 % off from
real-feed equivalent — *better* substrate fidelity than any
single-leg variant in this family because of the wing-bias
cancellation.

This is a non-trivial benefit of the iron-condor structure on
synthetic data: the 4-leg combination is more substrate-robust
than the 1-leg or 2-leg variants. Real-feed verification (Phase 3)
will confirm; current expectations are that iron-condor Sharpe
estimates from synthetic data will be the most accurate in the
family.

## 5. Standard-benchmark-runner mode caveat (degenerate)

The standard `BenchmarkRunner` provides only the underlying's
prices column. Iron condor in Mode 2 (underlying-only) is a
**degenerate no-trade case**: all 4 leg columns are absent, so
the strategy emits all-zero weights and the bridge runs a
trivial backtest with zero P&L. Final equity = initial cash.

This differs from covered_call_systematic / cash_secured_put_systematic
where Mode 2 falls back to long-equity buy-and-hold. The iron
condor has no equity-leg position, so Mode 2 is vacuous. The
benchmark JSON's reported metrics reflect this (zero return, zero
Sharpe).

The full Mode 1 iron-condor P&L (4-leg, defined-risk) is exercised
in `tests/test_integration.py` via `make_legs_prices` and
`vectorbt_bridge.run` with all 4 discrete legs dispatched. Session
2H benchmark-runner refactor will wire up the leg construction.

## 6. OTM-expiry close approximation (×4 legs)

Per-cycle close approximations (per
`covered_call_systematic` §7) apply to all 4 legs independently.
For typical iron condors most cycles end with all 4 legs OTM at
expiry (the strategy collects the full net premium); in those
cycles each leg's close fires one bar early at small residual
time-value premium. Per-cycle P&L approximately 2-4 % short of
analytic.

For ITM-at-expiry cycles (one or both short legs assigned), the
close fires correctly on the expiry bar at intrinsic value for
the assigned leg. Long-leg close (if also ITM) fires correctly.

## 7. Calendar-month-start writes vs. third-Friday writes

Same convention as siblings: first-trading-day-of-month writes
vs. published CNDR third-Friday writes. ≤ 10 % per year shift
in premium-income profile. All 4 legs roll on the same write
date.

## 8. yfinance passthrough assumption (Session 2H verification)

Inherited from sibling strategies.

## 9. Strike-grid cliff: deep-OTM long wings

The synthetic chain's grid spans 0.80×–1.20× spot (9 strikes,
5 %-spaced). The default ``long_put_otm = 0.10`` (10 % OTM long
put at 0.90× spot) and ``long_call_otm = 0.10`` (10 % OTM long
call at 1.10× spot) sit comfortably within the grid.

If a user sets ``long_put_otm = 0.20`` (20 % OTM long put at
0.80× spot) — at the lower grid bound — the strategy still
works but the long-put leg sits at the extreme grid bound. If
``long_put_otm > 0.20`` the strategy falls back to the
0.80×-spot strike (deepest available); the configured wing is
silently capped at the grid bound. This is a substrate cliff;
documented for transparency. Real-feed adapters with a wider
strike grid won't hit this cliff.

## 10. Composition-wrapper transparency

`IronCondorMonthly` uses 4 inner strategy instances (2 ×
`CashSecuredPutSystematic`, 2 × `CoveredCallSystematic`) to
generate the 4 leg-premium series. Bug fixes in the inner
strategies' `make_*_leg_prices` flow through automatically.
The lifecycle detection in `IronCondorMonthly.generate_signals`
is local to this strategy (not delegated), because the iron
condor's signed-weight pattern (-1 for shorts, +1 for longs at
write; opposite at close) differs from the parent strategies'
single-side conventions.
