# Known failure modes — cash_secured_put_systematic

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

Single-leg systematic 1-month 5 % OTM put write on synthetic
chains. The strategy will lose money in the regimes below; none
of these are bugs, they are the cost of the variance-risk-premium
exposure on a put-write.

## 1. Strong sustained equity downturns (2008 H2, 2020 March)

When SPY drops sharply through the 5 % OTM strike each month,
the put is assigned (intrinsic positive at expiry from the
short-put writer's perspective: strategy buys SPY at strike when
spot is below). The strategy holds long-equity at the assigned
price into a falling market — same drawdown trajectory as
SPY but mitigated by the premium income collected at write.

Expected behaviour for `cash_secured_put_systematic` in similar
regimes:

* Drawdown 80-90 % of SPY's drawdown in the same window
* Premium income offsets ~200-400 bps of the drag
* Recovery tracks SPY because the strategy owns the underlying
  post-assignment

CBOE PUT historically has a *lower* maximum drawdown than SPY
(per Whaley 2002 / CBOE methodology white paper) because the
collected premia accumulate in cash between assignments —
documented academically in Israelov-Nielsen 2014 §IV.

## 2. Vol-of-vol spikes (2018 February "Volmageddon", 2020 March COVID)

When realized vol spikes from a low base, the strategy is short
volatility into a vol expansion. The short-put leg's mark-to-
market loss can exceed the cash-collateral interest in the same
week — particularly near the strike on a sharp drop that moves
the put deep ITM.

Expected behaviour during sharp vol spikes:

* Drawdown of 5-12 % from peak in the spike week
* Recovery as the new monthly write captures the elevated premium
  (the IV the synthetic chain prices at scales with realized vol)

The synthetic-chain flat-IV substrate *materially understates*
the drawdown for puts specifically: real put-skew makes OTM puts
much more expensive than the synthetic chain's ATM-IV pricing,
and during vol-of-vol spikes the put-skew widens further (left
tail demand surges). The drawdown estimates above are calibrated
to real-feed literature, not to what the synthetic-chain backtest
would produce in isolation.

## 3. Strong cluster overlap with Phase 1 `cash_secured_put_proxy`

ρ ≈ 0.85-0.95 in neutral-to-rising-vol regimes; lower (0.5-0.7)
in strong-trending equity regimes.

Both strategies express the same economic content (short-vol
premium plus implicit long-equity exposure) but on different
substrates:

* Phase 1 `cash_secured_put_proxy` = realized-vol overlay
  (Ungar/Moran 2009, ADR-002 _proxy).
* Phase 2 `cash_secured_put_systematic` = explicit short-put leg
  priced from a synthetic chain (ADR-005 substrate) and dispatched
  via `discrete_legs` to `vectorbt SizeType.Amount` semantics.

This is the deliberate Phase-1-to-Phase-2 evolution. Both ship on
main: the proxy stays for users who want the single-column
equity-overlay form; the systematic version ships for users who
want the explicit two-column expression of the trade.

## 4. Expected cluster correlations with Session 2F siblings

* **`covered_call_systematic`** (Commit 2): ρ ≈ 0.95-1.00.
  Put-call parity equivalence on European-style synthetic
  options: long underlying + short call has the same payoff
  (ex-dividends) as +cash − short put. The synthetic-options
  adapter prices both legs off the same diffusion under BS, so
  the two strategies' monthly returns are near-identical in
  magnitude. They differ only in the leg construction (call
  write vs. put write); both ship as canonical Phase 2 forms.
* **`bxm_replication`** (Commit 4): ρ ≈ 0.90-0.95. Whaley 2002
  ATM-call write — same VRP exposure direction as this CSP.
* **`bxmp_overlay`** (Commit 5, reframed wheel): ρ ≈ 0.95-1.00
  during the put-write half of the cycle, lower during the
  covered-call half. Average ρ ≈ 0.85-0.95.
* **`short_strangle_monthly`** (Commit 7): ρ ≈ 0.70-0.85. The
  put-leg of the strangle correlates with this CSP; the call-leg
  diversifies.
* **`iron_condor_monthly`** (Commit 6): ρ ≈ 0.50-0.70. Capped
  short-vol vs uncapped short-vol; the iron-condor's capped
  tail diverges from this CSP's full-loss-on-deep-ITM tail.

## 5. Synthetic-chain substrate caveat (MORE severe for puts than calls)

The synthetic-options adapter (ADR-005) has flat IV across
strikes — no skew. For PUTS this is a *materially worse*
approximation than for calls because real put-skew (left-tail
risk premium for OTM puts) is large and persistent: real OTM
puts trade at IV 20-40 % higher than ATM IV in moderate-vol
regimes, expanding to 50-80 % during stress.

The strategy's monthly P&L on synthetic chains will *underestimate*
the premium income by approximately 10-20 % in moderate-skew
regimes — roughly double the underestimation
`covered_call_systematic` exhibits, because put-skew is steeper
than call-skew on equity indices. Real-feed verification with
skewed chains is deferred to Phase 3 with Polygon (ADR-004).

This is documented honestly: the synthetic backtest reflects
*signal-logic correctness* and *level approximation*, not real
PUT-index Sharpe.

## 6. Standard-benchmark-runner mode caveat

Same caveat as `covered_call_systematic`. Standard
`BenchmarkRunner` provides only the underlying's prices column;
strategy degrades to long-equity buy-and-hold. The full CSP P&L
(Mode 1, two-leg) is exercised in `tests/test_integration.py` via
`make_put_leg_prices`. Session 2H benchmark-runner refactor will
wire up the synthetic call-leg construction.

## 7. OTM-expiry close approximation

Same convention as `covered_call_systematic`: when the put
expires out-of-the-money, the leg's expiry-bar price is the flat
floor (intrinsic = 0); close fires one bar early at small
residual time-value premium. Per-cycle P&L approximately 1-2 %
short of the analytic premium-minus-zero-intrinsic. For ITM
expiries (assignment) the close fires correctly on the expiry
bar at intrinsic value.

## 8. Calendar-month-start writes vs. third-Friday writes

CBOE PUT index rolls on the third Friday of each month (option
expiration day). This implementation writes on the first trading
day of each calendar month, choosing the chain expiry that clears
a 25-day-DTE floor. Same convention and impact as
`covered_call_systematic` (≤10 % per year shift in
premium-income profile).

## 9. yfinance passthrough assumption (Session 2H verification)

Same assumption as `covered_call_systematic`: depends on the
synthetic-options adapter, which depends on the equities
`yfinance` adapter. Real-data shape verification deferred to
Session 2H. Integration tests mock the underlying feed via the
`_FakeUnderlying` pattern.
