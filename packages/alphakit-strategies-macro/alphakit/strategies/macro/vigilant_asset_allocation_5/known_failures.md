# Known failure modes — vigilant_asset_allocation_5

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

Keller-Keuning 2017 VAA-G4 on a 5-ETF universe (4 offensive
risky + 1 defensive cash). The strategy is **deliberately
discrete**: at any given month-end it holds exactly one ETF at
100%. The cost of that concentration + the discrete switching
logic is documented below.

## 1. Whipsaw in indecisive markets (2015-16, 2018, 2022 Q4)

The 13612W aggregator weights the 1-month return heavily (~63%
of the total score), so a single bad month can flip the canary
gate from risk-on to risk-off — and a single recovery month can
flip it back. In indecisive markets where assets oscillate without
establishing durable trends, the gate flips repeatedly, producing
high turnover and large transaction costs.

Historical examples:

* **2015 Q3 – 2016 Q1:** EEM dropped sharply in Aug 2015, flipping
  the canary off (EEM W < 0). EEM recovered in Oct 2015, flipping
  on. EEM dropped again in Jan 2016, off. Recovered in March,
  on. Three flips in 7 months × 200% notional per flip ≈ 600%
  total turnover.
* **2018 Q4:** The simultaneous Oct-Dec equity drawdown
  (-10-15% on SPY/EFA/EEM) flipped the canary off in November,
  caught the late-December bottom in cash, then flipped back on
  in February 2019 — missing the sharpest part of the recovery.
* **2022 Q4:** AGG had been negative since Q1 2022 (Fed
  tightening), keeping the strategy in SHY. The brief Nov 2022
  bond rally flipped AGG positive momentarily; the gate flipped
  on; then AGG turned negative again in December, flipping off.

Expected behaviour in indecisive regimes:

* Cumulative whipsaw cost of 3-8% per year vs a buy-and-hold of
  the same 5 ETFs.
* Sharpe of 0.0 to -0.3 over the whipsaw window.
* No catastrophic drawdown — the strategy is long-only and
  single-asset; whipsaw is the cost, not crash exposure.

## 2. Single-asset concentration risk

By construction the strategy holds exactly **one** ETF at any
given month-end. If that ETF takes a sharp idiosyncratic move
intra-month (an event the monthly rebalance cannot react to), the
entire portfolio takes that move.

Historical examples:

* **2020 March (COVID crash):** Entering March 2020 the strategy
  held SPY (positive 13612W from the 2019 equity rally). SPY
  dropped -34% peak-to-trough in 23 days — the strategy held the
  full move. The April rebalance flipped to SHY but the damage
  was done.
* **2022 Q2 (TLT drawdown):** Entering Q2 the strategy held SHY
  (risk-off from rates rising). SHY itself lost ~3% as the short
  Treasury curve repriced. Smaller loss than equity-exposed
  strategies but non-zero.

Expected behaviour during single-asset shocks:

* Max drawdown of 15-30% during equity-class shocks (if held).
* Max drawdown of 3-5% during defensive shocks (SHY duration
  repricing).

Mitigation: pair with a separate cross-asset overlay that holds
some weight in non-top-1 assets. Out of scope for the strict
VAA-G4 specification.

## 3. Defensive bucket collapsed to SHY only

Keller-Keuning 2017's VAA-G4 uses a 3-asset defensive bucket
(LQD / IEF / SHY) and picks the top-1 by 13612W among them. This
5-ETF variant collapses the defensive to SHY only — losing the
flexibility to rotate into LQD (credit) or IEF (mid-duration
Treasuries) in risk-off regimes.

Historical impact:

* **2008 Q4 GFC:** LQD recovered faster than SHY post-September
  2008 as credit spreads tightened. The 3-asset defensive variant
  would have rotated into LQD in late 2008; the 5-ETF variant
  stayed in SHY and missed ~3-5% relative outperformance.
* **2019:** IEF rallied as Treasury yields fell. The 3-asset
  variant would have rotated into IEF; the 5-ETF variant stayed
  in SHY and missed ~4-6%.

Expected impact: 1-3% per year in defensive periods. Phase 3
users can re-introduce the 3-asset defensive by composing this
strategy with a separate defensive-bucket picker that uses
13612W on (LQD, IEF, SHY).

## 4. Late-flip into defensive during sharp regime changes

The monthly rebalance + monthly returns means the canary gate
takes 1 full month to react to a regime change. During sharp
multi-month drawdowns the strategy holds the wrong asset for the
first month, takes the loss, then flips.

Historical examples:

* **2008 Sept-Oct GFC:** Strategy held SPY entering September
  (positive 13612W from Q2 2008). SPY -29% in 6 weeks. October
  month-end: flips to SHY. Loss is fully absorbed.
* **2020 March COVID:** Same pattern, compressed to weeks. Held
  SPY entering March; SPY -34% in 23 days; flipped to SHY at
  end-March.

Expected behaviour: catastrophic-event drawdowns of 15-25%
before the strategy flips. The breadth-momentum gate provides
crash *protection* against multi-month regime changes but not
against single-month crashes.

## 5. Rebalance-cadence: monthly signal, daily bridge-side drift correction

This strategy inherits the AlphaKit-wide convention: monthly
target signal emitted at month-end, daily bridge-side drift
correction by vectorbt's ``SizeType.TargetPercent`` semantics.
For VAA specifically, this means:

* On bars *between* rotation events, the bridge holds the
  current top-1 ETF at ~1.0 weight, drift-correcting daily.
* On bars *at* a rotation event (the gate flips, or the top-1
  offensive changes), the bridge executes a 200%-notional swap
  (-1.0 on the old leg, +1.0 on the new leg).

Empirical trade-event count: **~63 events per asset per year for
the held leg** (drift correction) + **0-3 rotation events per
year** (full 200% swaps). The full audit trail of the cadence
convention is in ``docs/phase-2-amendments.md`` "Session 2G:
alphakit-wide rebalance-cadence convention".

## 6. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **Phase 1 `dual_momentum_gem`** (trend family, Antonacci 2014)
  — closest cluster sibling. Both use discrete momentum-based
  rotation with a defensive cash-bucket fallback. Expected ρ ≈
  **0.40–0.60** (correlated direction in clear regimes;
  uncorrelated during transitional periods when the more-
  reactive 13612W and the 12-month signal disagree).
* **Phase 2 Session 2G `gtaa_cross_asset_momentum`** (Commit 3,
  AMP 2013 §V) — same broad-asset universe but continuous-vol-
  scaled long-short weights instead of discrete top-1 /
  defensive rotation. Expected ρ ≈ 0.30–0.50.
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  static 25/25/25/25 allocator. Expected ρ ≈ 0.20–0.40 (the
  VAA strategy goes to extreme concentration positions that the
  permanent portfolio's diversified design does not).
* **Phase 1 `tsmom_12_1`** (trend family) — single-horizon
  vol-scaled TSMOM on a similar universe. Expected ρ ≈
  0.20–0.40 (different shape entirely).

These overlaps are expected. The closest expected ρ (0.40-0.60
with `dual_momentum_gem`) is well below the Phase 2 master
plan §10 deduplication-review bar (ρ > 0.95).

## 7. NaN / warmup behaviour

Before 12 months of price history are available per ETF, at
least one of the (r_1, r_3, r_6, r_12) returns is NaN. The
strategy fills NaN scores with -∞ so the canary check correctly
treats warmup as "any-negative" and the strategy emits zero
weights everywhere during warmup. The bridge interprets this as
"hold 100% cash".

This is documented in the strategy module docstring's "Edge
cases" section.

## Regime performance (reference, from Keller-Keuning 2017 Table 4)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Disinflation (1981-2000) | full window | ~0.85 | −10% |
| Dotcom + bear (2000-03) | 2000-01 – 2003-12 | ~0.6 (defensive ~50% of time) | −8% |
| Pre-GFC bull (2003-07) | 2003-04 – 2007-09 | ~1.1 | −6% |
| GFC defensive (2007-09) | 2007-10 – 2009-03 | ~0.4 (mostly in SHY) | −14% |
| Post-GFC reflation (2009-14) | 2009-04 – 2014-12 | ~0.7 | −12% |
| Range-bound (2015-18) | 2015-01 – 2018-12 | ~0.2 | −15% (whipsaw) |
| Real-rate spike (2022) | 2022-01 – 2022-12 | ~−0.3 | −18% |

(Reference ranges from Keller-Keuning 2017 Table 4 + practitioner
sources; the in-repo benchmark is the authoritative source for
this implementation — see
[`benchmark_results.json`](benchmark_results.json).)
