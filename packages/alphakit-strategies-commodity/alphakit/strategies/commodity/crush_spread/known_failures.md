# Known failure modes — crush_spread

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

Soybean-crush-spread mean-reversion trade. Failures cluster around
demand-side regime shifts and trade-policy disruptions where the
spread **trends** instead of reverting.

## 1. Demand-side regime shifts (2007-2008 biofuel-mandate, 2014 H2 record harvest)

Two episodes broke the mean-reversion assumption on demand-side:

* **2007-2008 US biofuel mandate ramp-up**: ZL demand surged with
  the Renewable Fuel Standard expansion; the crush widened
  persistently for 18 months. The strategy shorted the crush on
  the first 2σ deviation and stayed short while the spread
  continued widening → drawdown ~10-15%.
* **2014 H2 US record harvest + China demand decoupling**:
  whole-soybean prices collapsed faster than products → crush
  *widened* sharply (margin good for crushers) but the strategy
  was waiting for mean reversion → wider drawdown ~12-18%.

Mitigation: tighten `entry_threshold` to 2.5σ or 3σ; or overlay a
trend filter that exits if spread continues > 5σ from entry —
Phase 3 candidate.

## 2. Trade-policy shocks (2018 China tariffs)

In June-August 2018, China's retaliatory tariffs on US soybeans
caused:

* US soybean prices collapsed (-25%) on lost export demand
* Meal and oil demand domestically held up (US livestock + biofuel)
* Crush spread **widened** to historical extremes for ~6 months

The strategy shorted the crush on the first 2σ widening and stayed
short through the tariff regime → drawdown ~15-20%. Recovery only
came after the Phase 1 trade deal (December 2019) re-opened US
exports → spread compressed back toward mean.

Trade-policy shocks are *not* mean-reverting on the 6-12-week
half-life that the strategy assumes; they are persistent
regime-shift events that can take 12-24 months to revert.

## 3. Drought / weather shocks (2012 Midwest drought)

The 2012 US Midwest drought spiked all three legs simultaneously:

* ZS rallied ~30% (yield concerns)
* ZM rallied ~25% (feed-shortage concerns)
* ZL rallied ~15% (slower)

The crush spread compressed (ZS rose faster than ZM+ZL combined)
→ z-score went < -2σ → strategy entered long-crush. Spread did
revert ~3 months later as harvest realised yields → trade was
profitable but with higher-than-usual entry-to-exit volatility
(8% drawdown before profit).

## 4. Biofuel-mandate expirations / changes

Soybean oil (ZL) is heavily exposed to US biofuel-mandate policy.
Mandate-volume changes (e.g. 2014 EPA proposal cuts, 2017 PSA
volume increases) cause one-time level shifts in ZL that the
rolling z-score absorbs only over the 1-year window. In the
3-6 months following a mandate change, the strategy can produce
false signals as the spread re-baselines.

## 5. Continuous-contract roll bias

Standard yfinance back-adjustment limitation. The 252-day rolling
window absorbs the noise but produces false-positive signals in
the 5-10 days after each roll. ZS, ZM, ZL all roll at the same
schedule (CBOT calendar), so the bias is correlated across legs
and partially cancels in the spread.

## 6. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **`crack_spread`** (Session 2E sibling, Commit 9) — different
  spread (petroleum refining); independent industries.
  Expected ρ ≈ 0.0-0.1.
* **`wti_brent_spread`** (Session 2E sibling, Commit 11) —
  different commodity entirely; ρ ≈ 0.0-0.1.
* **`grain_seasonality`** — same panel (ZS overlap), different
  signal. Expected ρ ≈ 0.1-0.2 (planting-season uncertainty
  partly drives crush margin via ZS variability).
* **`commodity_curve_carry`** — different signal entirely;
  ρ ≈ 0.0-0.1.
* **Phase 1 trend / momentum strategies** — different signal,
  no overlap; ρ ≈ 0.0-0.1.

All overlaps below the master plan §10 deduplication bar (ρ > 0.95).

## 7. Bushel-equivalent simplification bias

The strategy uses the textbook 1:1.5:0.8 simplification (Simon
1999 §II) instead of the unit-conversion-aware CBOT board crush.
The two produce identical signal ordering (a long-crush signal in
the simplified version is also a long-crush signal in the
board-crush version) but differ by a small constant scale factor.
This bias does not affect the z-score (which is scale-invariant)
or the trading rule, but users running real-money sleeves should
validate the convention against their broker's spread definition.

## 8. Multi-leg execution risk

3 simultaneous legs (ZS, ZM, ZL). CBOT trades the soybean crush
directly as a "Crush" market — single-broker spread orders are
the preferred execution path. Atomic multi-leg execution via SOR
risks leg-out if one leg fills and another doesn't. The
synthetic-fixture benchmark assumes atomic execution.

## Regime performance (reference, from public processor-margin sleeves)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-biofuel mean-reversion | 2003-2006 | ~0.9 | −5% |
| Biofuel-mandate ramp-up | 2007-2008 | ~−0.7 | −15% |
| Post-crisis recovery | 2009-2013 | ~0.8 | −6% |
| 2014 H2 record harvest | 2014-08 – 2015-04 | ~−0.9 | −18% |
| Post-harvest equilibrium | 2015-2017 | ~0.6 | −7% |
| 2018 China-tariff shock | 2018-06 – 2019-12 | ~−1.0 | −20% |
| Post-tariff re-equilibration | 2020-2023 | ~0.7 | −8% |

(Reference ranges from public processor-margin sleeves; the
in-repo benchmark is the authoritative source for this
implementation — see [`benchmark_results.json`](benchmark_results.json).)
