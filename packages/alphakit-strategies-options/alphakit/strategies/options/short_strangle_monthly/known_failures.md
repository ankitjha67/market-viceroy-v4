# Known failure modes — short_strangle_monthly

> Phase 2 2-leg short-volatility monthly strangle write on
> synthetic chains. Coval/Shumway 2001 foundational + Bondarenko
> 2014 primary methodology. The strategy will lose money in the
> regimes below; none are bugs — they are the cost of the
> uncapped short-vol exposure.

## 1. Sustained directional moves through either short strike

When the underlying moves through either short strike (10 % OTM)
and stays there into expiry, the breached short leg is assigned
ITM with **uncapped** loss — the strangle has no protective
wings (unlike the iron condor). Per-cycle loss is
(intrinsic at expiry − net premium received) × number of
contracts, which can substantially exceed the per-cycle premium
income.

Expected behaviour for `short_strangle_monthly` in similar
regimes:

* Single-cycle losses of $10-$30 per contract on a $100
  underlying when realised vol drives the underlying
  through a strike (compare ~$5 max-loss-per-contract on
  iron_condor_monthly).
* Multi-month directional trends produce compounded losses;
  consecutive-month losses of 4-6 cycles before flattening.
* Drawdown 12-25 % from peak in sustained-trend windows
  (notably worse than iron condor's 8-15 % under the same
  windows).

## 2. Vol-of-vol spikes (2018 February, 2020 March)

More severe than capped variants (iron condor) because the
short legs' mark-to-market loss is not offset by long-wing
gains. The 2018 February "Volmageddon" and 2020 March COVID
crash both produced single-month losses of >25 % on
naive short-strangle books per Bondarenko follow-up papers.

Expected behaviour during sharp vol spikes:

* Drawdown of 10-20 % from peak in the spike week (vs iron
  condor's 4-8 %)
* Recovery dynamics: slow — the elevated post-spike IV does
  re-fund the next cycle's premia, but the cumulative
  drawdown takes 6-12 months to recover under typical
  post-stress vol-of-vol decay.

The synthetic chain's flat-IV substrate **materially
understates** the strangle's stress-period drawdown because
real put-skew widens dramatically under stress (the put leg
sees the worst of it). Real-feed verification (Phase 3
Polygon) will show meaningfully larger drawdowns than the
synthetic backtest.

## 3. Cluster overlap with siblings

* **`iron_condor_monthly`** (Commit 6): ρ ≈ 0.85-0.95.
  Iron condor IS short strangle plus wings.
* **`bxmp_overlay`** (Commit 5): ρ ≈ 0.80-0.90. BXMP
  is short strangle PLUS long underlying.
* **`covered_call_systematic`** (Commit 2): ρ ≈ 0.70-0.85.
  Strangle captures call+put VRP; covered call only the
  call side plus equity beta.
* **`cash_secured_put_systematic`** (Commit 3): ρ ≈ 0.70-0.85.
  Strangle captures both sides; CSP only the put side with
  implicit equity exposure.

## 4. Synthetic-chain substrate caveat (compounded for 2 legs)

The strangle's 2 short legs at 10 % OTM both sit in the wings
where real put-skew effects matter:

* Short put @ 10 % OTM: ~15-25 % premium underestimation
  (real put-skew steep at this offset).
* Short call @ 10 % OTM: ~5-10 % premium underestimation.

Net effect: the strangle's per-cycle premium income on
synthetic chains is approximately 10-15 % short of real-feed
equivalent. Tail-risk understatement (per §2 above) is the
larger concern — the synthetic backtest is *too rosy* on
both income (slightly low) AND tail risk (markedly low).

## 5. Standard-benchmark-runner mode caveat (degenerate)

Same as `iron_condor_monthly` §5: standard `BenchmarkRunner`
provides only the underlying's prices column → all-zero weights,
no-trade backtest, final equity = initial cash. Mode 1 full
strangle P&L exercised in `tests/test_integration.py`. Session
2H benchmark-runner refactor will wire up the leg construction.

## 6. OTM-expiry close approximation (×2 legs)

Per-cycle close approximations apply to both short legs. Most
cycles end with both legs OTM at expiry; in those cycles each
leg's close fires one bar early at small residual time-value
premium. Per-cycle P&L approximately 1-3 % short of analytic.

For ITM-at-expiry cycles (one or both legs assigned), the
close fires correctly on the expiry bar at intrinsic value.

## 7. Calendar-month-start writes vs. third-Friday writes

Same convention as siblings.

## 8. yfinance passthrough assumption (Session 2H verification)

Inherited from sibling strategies.

## 9. Composition-wrapper transparency

`ShortStrangleMonthly` uses 2 inner strategy instances (1 ×
`CashSecuredPutSystematic`, 1 × `CoveredCallSystematic`). Bug
fixes in the inner strategies' `make_*_leg_prices` flow through
automatically.
