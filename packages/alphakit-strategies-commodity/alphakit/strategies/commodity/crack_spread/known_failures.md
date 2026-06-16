# Known failure modes — crack_spread

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

3-2-1 crack-spread mean-reversion trade. Failures cluster around
regimes where the spread **trends** instead of reverting —
typically driven by structural supply/demand shifts that the
1-year rolling lookback cannot adapt to fast enough.

## 1. Structural-regime shifts (2008 H2, 2014-2015 shale, 2020 H1 COVID)

Three episodes broke the mean-reversion assumption:

* **2008 H2 demand collapse**: refining margins compressed from
  $25/bbl to negative as demand evaporated; the spread stayed
  below the rolling mean for 6+ months. The strategy entered
  long-crack on the first 2σ deviation and stayed long through
  the entire decline → drawdown ~12-18%.
* **2014-2015 shale-supply surge**: US crude oversupply pushed
  CL down faster than RB/HO; the crack widened to historically
  high levels (well above the rolling 2σ band). The strategy
  shorted the crack and stayed short while the spread continued
  widening → drawdown ~15-20%.
* **2020 H1 COVID demand shock**: gasoline demand collapsed
  faster than crude demand; crack went deeply negative for ~3
  months. The strategy entered long-crack early and the spread
  continued to compress before reverting → drawdown ~10-15%.

Expected behaviour during regime shifts:

* Drawdown 10-20% over 3-6 months
* Recovery typically takes 6-12 months as the rolling lookback
  re-baselines and the spread completes mean reversion to the
  new level

Mitigation: tighten `entry_threshold` to 2.5σ or 3σ to require
more extreme dislocations before entering; or overlay a regime
filter (e.g. exit if the spread trends > 5σ away from entry
without reversion) — Phase 3 candidate.

## 2. Hurricane / refinery-outage events

Sudden refinery-capacity loss (2005 Katrina, 2017 Harvey, 2021
Ida) causes:

* Short-term **product shortage** → RB and HO spike → crack
  widens to the upside
* Refinery-restart phase (typically 2-6 weeks later) → product
  surplus → crack compresses

The strategy shorts the crack on the initial widening and stays
short through the restart phase, eventually winning on the
compression. But the intermediate volatility is high — drawdown
can be 5-10% in the 4-8-week event window before profitability.

Expected behaviour during hurricane events:

* Initial drawdown 5-10% as crack continues to widen
* Recovery within 4-8 weeks as refining capacity restores

## 3. Heating-oil / gasoline seasonality (winter, summer-driving)

The 3-2-1 ratio assumes equal seasonal demand for gasoline and
heating oil. In practice:

* Summer: gasoline demand spikes (driving season), heating oil
  demand collapses → crack composition shifts toward gasoline-
  premium dominance
* Winter: heating oil demand spikes (US Northeast cold) → crack
  composition shifts toward heating-oil-premium dominance

Both seasonal effects are *small* (~3-5% of the spread) but
cumulative over a multi-year backtest produces a slight bias
that the rolling z-score absorbs only partially. Users wanting
a tighter strategy should consider seasonal-adjusted z-scores
(Phase 3 candidate).

## 4. RBOB transition in 2006

In 2006 NYMEX gasoline futures transitioned from "HU" (unleaded
gasoline) to "RB" (RBOB). The two contracts are not identical —
RB excludes the ethanol component and trades at a slight
discount to HU. Backtests spanning the transition need to splice
the contract series carefully; yfinance's `RB=F` continuous
series has the splice baked in but the historical data
discontinuity around July 2006 introduces noise in the rolling
z-score.

## 5. Continuous-contract roll bias

Standard yfinance back-adjustment limitation: continuous-contract
roll boundaries introduce small level discontinuities that
contaminate the z-score in the 5-10 days immediately after each
roll. The 252-day rolling window absorbs the noise but the
strategy can produce false-positive signals in the post-roll
window. Real-feed Session 2H benchmarks should use explicit
per-contract data with documented roll convention.

## 6. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **`crush_spread`** (Session 2E sibling, Commit 10) — different
  spread (soybean processing margin); independent industries.
  Expected ρ ≈ 0.0-0.1.
* **`wti_brent_spread`** (Session 2E sibling, Commit 11) —
  different spread (WTI vs Brent geographic) but both involve
  crude. Expected ρ ≈ 0.1-0.3.
* **`wti_backwardation_carry`** — different signal; ρ ≈ 0.0-0.2.
* **`commodity_curve_carry`** — different signal; ρ ≈ 0.0-0.2.
* **Phase 1 trend / momentum strategies** — different signal,
  different universe; ρ ≈ 0.0-0.1.

All overlaps below the master plan §10 deduplication bar (ρ > 0.95).

## 7. Multi-leg execution risk

The strategy holds 3 simultaneous legs (CL, RB, HO). Real-world
execution at multi-leg spread prices requires:

* Single-broker spread orders (NYMEX trades the 3-2-1 crack
  directly as a "Cracks" market) — preferred path.
* Or atomic multi-leg execution via SOR — risk of leg-out if
  one leg fills and another doesn't.

The synthetic-fixture benchmark assumes atomic execution; real-
feed Session 2H should test against multi-leg slippage models.

## Regime performance (reference, from public energy-spread sleeves)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-shale mean-reversion | 2003-2007 | ~1.0 | −5% |
| 2008 demand collapse | 2008-09 – 2009-03 | ~−1.5 | −18% |
| Post-crisis recovery | 2009-2013 | ~0.6 | −7% |
| Shale-glut regime shift | 2014-06 – 2016-06 | ~−0.8 | −15% |
| Post-shale equilibrium | 2017-2019 | ~0.7 | −6% |
| COVID dislocation | 2020-03 – 2020-09 | ~−1.0 | −12% |
| Post-COVID re-equilibration | 2021-2023 | ~0.9 | −7% |

(Reference ranges from public energy-spread sleeves; the in-repo
benchmark is the authoritative source for this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
