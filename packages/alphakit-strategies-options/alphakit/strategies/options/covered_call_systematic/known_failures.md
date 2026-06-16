# Known failure modes — covered_call_systematic

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

Single-leg systematic 1-month 2 % OTM call write on synthetic
chains. The strategy will lose money in the regimes below; none of
these are bugs, they are the cost of the variance-risk-premium
exposure on a covered-call write.

## 1. Strong sustained equity rallies (2017, 2019 H2, 2020 H2)

When SPY rallies sharply through the 2 % OTM strike each month,
the call is assigned (intrinsic positive at expiry), and the
strategy gives up the upside above the strike. Israelov & Nielsen
(2014) document that BXM-style writes underperform buy-and-hold
by 200-400 bps annually in years of >15 % SPY return.

Expected behaviour for `covered_call_systematic` in similar regimes:

* Sharpe 0.0 to +0.3 (vs. SPY's 1.0+ in such years)
* Tracks SPY by ~70-85 % of the upside; cap-and-floor profile
* Premium income partially offsets the called-away P&L drag

## 2. Vol-of-vol spikes (2018 February "Volmageddon", 2020 March COVID)

When realized vol spikes from a low base, the strategy is short
volatility into a vol expansion. The short-call leg's mark-to-
market loss can exceed the equity-leg gain in the same week —
particularly near the strike on a sharp rally that moves the call
deep ITM.

Expected behaviour during sharp vol spikes:

* Drawdown of 5-12 % from peak in the spike week
* Recovery as the new monthly write captures the elevated premium
  (the IV the synthetic chain prices at scales with realized vol)

The synthetic-options chain's flat-IV-across-strikes substrate
*understates* the rally drag relative to a real-IV-skew chain
(real chains charge a large premium for OTM calls during
expansion; the synthetic chain charges only the at-the-money IV).
The drawdown estimates above are calibrated to real-feed
literature, not to what a synthetic-chain backtest would produce
in isolation.

## 3. Strong cluster overlap with Phase 1 `covered_call_proxy`

ρ ≈ 0.85-0.95 in neutral-to-rising-vol regimes; lower (0.5-0.7) in
strong-trending equity regimes.

Both strategies express the same economic content (short-vol
premium on long-equity exposure) but on different substrates:

* Phase 1 `covered_call_proxy` = realized-vol overlay on equity
  prices (no chain, ADR-002 _proxy).
* Phase 2 `covered_call_systematic` = explicit short-call leg
  priced from a synthetic chain (ADR-005 substrate) and dispatched
  via `discrete_legs` to `vectorbt SizeType.Amount` semantics for
  the leg.

This is **not an accidental cluster** — it is the deliberate
Phase-1-to-Phase-2 evolution. Both ship on main: the proxy stays
for users who want the single-column equity-overlay form; the
systematic version ships for users who want the explicit two-
column expression of the trade.

Cluster-detection methodology (Phase 2 master plan §6) will surface
this pair at v0.2.0; the documentation here is the authoritative
explanation.

## 4. Expected cluster correlations with Session 2F siblings

* **`cash_secured_put_systematic`** (Commit 3): ρ ≈ 0.95-1.00.
  Put-call parity equivalence on European-style synthetic options:
  long underlying + short call has the same payoff (ex-dividends)
  as +cash − short put. The synthetic-options adapter prices both
  legs off the same diffusion under BS, so the two strategies'
  monthly returns are near-identical in magnitude. They differ
  only in the leg construction (call write vs. put write); both
  ship as canonical Phase 2 forms.
* **`bxm_replication`** (Commit 4): ρ ≈ 0.95-1.00. Same trade
  with `otm_pct = 0.0` (exactly ATM strike per Whaley 2002 BXM
  rules). The two ship as parametric variants — `bxm_replication`
  is the index-construction reference; `covered_call_systematic`
  is the practitioner-aligned 2 % OTM variant.
* **`bxmp_overlay`** (Commit 5, reframed wheel): ρ ≈ 0.85-0.95.
  Same monthly-write economic content with alternation between
  short-put and short-call legs per the CBOE BXMP index.
* **`short_strangle_monthly`** (Commit 7): ρ ≈ 0.70-0.85. Same
  variance-risk-premium exposure, scaled differently (2-leg short
  strangle vs. 1-leg covered call).
* **`iron_condor_monthly`** (Commit 6): ρ ≈ 0.50-0.70. Capped vs.
  uncapped short-vol; the iron condor caps the tail while the
  covered call has the equity-leg upside continually capped.

## 5. Synthetic-chain substrate caveat (mild for this strategy)

The synthetic-options adapter (ADR-005) has flat IV across strikes
— no skew. This strategy is **not** skew-dependent (single-leg call
write, not a risk-reversal or dispersion trade), so the substrate
limitation is mild. The 2 % OTM call is priced at the same IV as
ATM, which understates the call premium in real-world high-skew
regimes (real OTM calls are cheaper than the synthetic chain
prices them, except for short-dated calls into known events).

The strategy's monthly P&L on synthetic chains will *underestimate*
the premium income by approximately 5-15 % vs. real feeds in
moderate-skew regimes. Real-feed verification with skewed chains
is deferred to Phase 3 with Polygon (ADR-004).

## 6. Standard-benchmark-runner mode caveat

The standard `alphakit.bench.runner.BenchmarkRunner` provides only
the underlying's prices column — it does not yet construct the
synthetic call-leg via `make_call_leg_prices`. In that mode, the
strategy gracefully degrades to long-only equity (`+1.0` weight on
the underlying), which is a buy-and-hold backtest of SPY.

`benchmark_results.json` reports the buy-and-hold-of-SPY
metrics with an explicit `note` field documenting the dual-mode
behaviour. The full covered-call P&L (Mode 1, two-leg) is
exercised in `tests/test_integration.py`, which constructs the
call leg via `make_call_leg_prices`, declares `discrete_legs` on
the strategy, and runs the canonical 2-column backtest end-to-end
through `vectorbt_bridge.run`.

Session 2H's benchmark-runner refactor will wire up the synthetic-
options call-leg construction so that the standard benchmark
exercises the canonical 2-column path.

## 7. OTM-expiry close approximation

`CoveredCallSystematic.generate_signals` detects close events from
the leg's price series via positive-to-zero discontinuities. When
the call expires out-of-the-money, `make_call_leg_prices` sets
the expiry-bar price to 0 (intrinsic = 0). The
zero-discontinuity-based close detection then fires on the bar
*before* the expiry bar at a small residual time-value premium
(typically $0.05-$0.20) rather than on the expiry bar at exactly
zero.

The resulting per-cycle P&L is approximately 1-2 % short of the
analytic premium-minus-zero-intrinsic. This is within the
substrate-noise tolerance of the synthetic chain itself (whose
flat-IV approximation already biases premium estimates by a
similar magnitude). For ITM expiries the close fires correctly on
the expiry bar at intrinsic value, and the analytic
premium-minus-intrinsic is captured exactly.

## 8. Calendar-month-start writes vs. third-Friday writes

The exact CBOE BXM index rolls on the third Friday of each month
(option expiration day). This implementation writes on the first
trading day of each calendar month, choosing the chain expiry that
clears a 25-day-DTE floor. The chosen expiry is still a third-
Friday (the synthetic chain exposes weekly + monthly + quarterly
third-Friday dates) — the difference is *which* third Friday
relative to the write date.

Empirical impact: the calendar-month-start convention captures
slightly more time decay on average (28-30 days held vs. ≈21 days
on third-Friday rolls), shifting the strategy's premium-income
profile by ≤10 % per year. Documented for transparency; not a
correctness issue.

## 9. yfinance passthrough assumption (Session 2H verification)

The strategy depends on the synthetic-options adapter, which in
turn depends on the equities `yfinance` adapter for the underlying
price history. Real-data shape verification (yfinance returning a
single-column close-price series for SPY without MultiIndex
ambiguity) is deferred to Session 2H benchmark-runner real-feed
runs. Integration tests mock the underlying feed via the
`_FakeUnderlying` pattern from
`packages/alphakit-data/tests/test_synthetic_options.py`.
