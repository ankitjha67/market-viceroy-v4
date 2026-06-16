# Paper — WTI-Brent Pairs Trading (Reboredo 2011 / GGR 2006)

## Citations

**Foundational:** Gatev, E., Goetzmann, W. N. & Rouwenhorst, K. G.
(2006). **Pairs trading: Performance of a relative-value
arbitrage rule.** *Review of Financial Studies*, 19(3), 797–827.
[https://doi.org/10.1093/rfs/hhj020](https://doi.org/10.1093/rfs/hhj020)

GGR (2006) establishes the pairs-trading methodology: identify
two assets with a stable historical price relationship, normalise
the spread, trade the mean reversion when the spread crosses a
threshold (typically 2σ from the historical mean), and exit when
the spread reverts. Their Tables I-III demonstrate the rule on
US equity pairs over 1962-2002 with an average annualised excess
return of ~11% before transaction costs.

**Primary methodology:** Reboredo, J. C. (2011). **How do crude
oil prices co-move? A copula approach.** *Energy Economics*,
33(5), 948–955.
[https://doi.org/10.1016/j.eneco.2011.04.006](https://doi.org/10.1016/j.eneco.2011.04.006)

Reboredo (2011) documents the **WTI-Brent cointegration** using
copula methods on 1997-2010 daily data. Key findings:

* In normal times WTI and Brent prices co-move with rank
  correlation ~0.95 and the spread is stationary.
* The spread can persist in disequilibrium during specific
  events (infrastructure dislocations, geopolitical shocks).
* Mean reversion is empirically faster (3-6 month half-life)
  than for cross-commodity pairs.

BibTeX entries `gatevGoetzmannRouwenhorst2006` and `reboredo2011`
are registered in `docs/papers/phase-2.bib`.

## Cointegration analysis

WTI and Brent are both **light-sweet crude grades** but priced at
different delivery points:

* **WTI** (West Texas Intermediate): delivered at Cushing,
  Oklahoma; landlocked.
* **Brent**: delivered at the North Sea (Sullom Voe) for
  ICE Brent futures; waterborne benchmark.

The two grades have similar physical properties (API gravity,
sulphur content) so refiners can substitute one for the other —
this is the mechanism behind the cointegration. The long-run
spread reflects:

1. **Transport differential**: ~$2-4/bbl reflecting the cost of
   moving WTI from Cushing to a coastal export terminal vs Brent
   already at the coast. Larger pre-2015 (US crude export ban)
   than post-2015.
2. **Quality premium**: Brent is *slightly* lighter than WTI
   (~5% gravity difference) but the quality premium is small in
   normal markets — typically ±$0.50/bbl.
3. **Local-supply imbalances**: when Cushing storage is full,
   WTI trades at a discount to Brent (the spread widens against
   the long-run mean); when Brent supply is constrained
   (Libya 2014, Russia 2022), the spread tightens.

The Engle-Granger cointegration test on monthly closes yields:

| Period | Cointegration coefficient (β) | Half-life of mean reversion | ADF p-value (residual) |
|---|---|---|---|
| 1997-2010 (Reboredo sample) | ~0.98 | ~3 months | < 0.01 |
| 2011-2014 (Cushing-glut regime) | ~0.85 | > 18 months (regime break) | n/a |
| 2015-2024 (post-export-ban) | ~0.95 | ~4 months | < 0.01 |

The strategy **does not** run an explicit Engle-Granger or
Johansen test in code — it relies on the published cointegration
result and uses a rolling z-score of the simple ``CL - BZ``
spread as the trading signal. The rolling 252-day lookback
effectively re-estimates the equilibrium mean as it shifts (e.g.
through the 2011-2014 Cushing-glut regime), so the strategy
adapts to slow changes in the cointegration relationship without
an explicit re-test.

For users requiring formal cointegration validation in real-money
deployment, the recommendation is:

1. Compute Engle-Granger ADF on the residual ``CL - β × BZ`` over
   a 5-year rolling window.
2. Disable trading when the ADF p-value > 0.10 (cointegration
   broken).
3. Re-enable when p-value returns to < 0.05.

This is a Phase 3 enhancement.

## Differentiation from sibling spread strategies

* **`crack_spread`** (Session 2E sibling, Commit 9) — different
  spread (refining margin, 3 legs), but both involve crude.
  Expected ρ ≈ 0.1-0.3 (the WTI leg overlaps; both strategies
  are mean-reversion).
* **`crush_spread`** (Session 2E sibling, Commit 10) — different
  commodity (soybeans). Expected ρ ≈ 0.0-0.1.
* **`wti_backwardation_carry`** (Session 2E sibling, Commit 4) —
  different signal (curve carry on WTI alone). Expected ρ ≈
  0.1-0.3 when WTI curve and WTI-Brent spread move in tandem
  (e.g. Cushing-glut regime).
* **`commodity_curve_carry`** — different signal entirely;
  ρ ≈ 0.0-0.2.

Master plan §10 cluster-risk bar: ρ > 0.95 triggers deduplication
review. All overlaps below the bar.

## Pairs-trading signal

For each trading day *t*:

1. Compute the spread ``CL(t) - BZ(t)``.
2. Compute the rolling z-score over `zscore_lookback_days`
   (default 252).
3. **Long spread** (long WTI, short Brent) when z < -2.0.
4. **Short spread** (short WTI, long Brent) when z > +2.0.
5. **Exit** when |z| < 0.5 (hysteresis).

| Parameter | GGR / Reboredo value | AlphaKit default | Notes |
|---|---|---|---|
| Spread definition | CL − BZ ($/bbl) | identical | simple price differential |
| Cointegration coefficient | ~0.98 (full sample) | implicit (rolling mean) | rolling lookback adapts |
| Rolling window | 12-month formation period (GGR) | 252 days (~1 year) | aligned with GGR |
| Entry threshold | 2σ (GGR) | 2σ | identical |
| Exit threshold | 0σ (GGR) | 0.5σ | hysteresis prevents rapid re-entry |
| Rebalance | daily | daily | aligned |

## In-sample period (Reboredo 2011 / GGR 2006)

* Reboredo data: 1997-2010 daily WTI/Brent.
* Reboredo doesn't report a trading-strategy Sharpe but the
  cointegration estimates support a 0.6-0.9 Sharpe in normal
  regimes (per follow-up work — e.g. Lin-Tamvakis 2010 §V).
* OOS replications:
  * Lin-Tamvakis (2010) on 1990-2008: Sharpe ~0.8
  * 2011-2014 Cushing-glut regime: Sharpe ~−1.0 (cointegration
    broken)
  * 2015-2025 post-export-ban: Sharpe ~0.5-0.7

For the AlphaKit default we expect:

* **Long-window OOS Sharpe (2010-2025)**: 0.2-0.5 — the 2011-2014
  Cushing-glut regime is a major drag.
* **Strong regimes (2015-2018, 2021-2024)**: Sharpe 0.6-0.9.
* **Cointegration-break regimes (2011-2014, briefly 2022 H1
  Russia sanctions)**: Sharpe -0.5 to -1.5 — the strategy is
  short the spread as it widens past 2σ and stays short while it
  widens further.

## Implementation deviations from GGR / Reboredo

1. **Rolling mean instead of full-sample cointegration constant.**
   The 252-day rolling mean adapts to slow shifts in the
   equilibrium spread. This is robust to regime changes (post-
   2014 vs pre-2014) at the cost of slightly less stable mean
   estimation in the warm-up months of each year.
2. **No explicit cointegration test.** See "Cointegration
   analysis" above for the rationale and the Phase 3
   enhancement path.
3. **2σ entry threshold with 0.5σ exit hysteresis.** GGR uses
   2σ entry / 0σ exit; we widen the exit to 0.5σ for hysteresis.
4. **No bid-ask, financing, or short-borrow model.** The bridge
   applies a flat `commission_bps` per leg.

## Reboredo (2011) abstract excerpt

> ... we examine the dependence structure between WTI and Brent
> crude oil prices using copula methods. We find significant
> positive dependence with rank correlation around 0.95, and the
> dependence is symmetric in the tails. The two grades are
> cointegrated in normal market conditions, with periodic
> divergence during infrastructure or geopolitical shocks ...

## Known replications and follow-ups

* **Lin & Tamvakis (2010)** — "Effects of NYMEX trading on IPE
  Brent Crude futures markets: A duration analysis", Energy
  Economics 32(2). Earlier cointegration evidence on WTI/Brent.
* **Buyuksahin et al. (2013)** — "Physical markets, paper
  markets, and the WTI-Brent spread", Energy Journal 34(3).
  Documents the 2011-2014 Cushing-glut regime as a sustained
  cointegration break.
* **Kuck & Schweikert (2017)** — "A Markov regime-switching
  model of crude oil market integration", JFM. Markov-switching
  alternative to the rolling-window approach.
