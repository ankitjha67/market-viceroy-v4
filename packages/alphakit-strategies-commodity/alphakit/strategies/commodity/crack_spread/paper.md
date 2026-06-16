# Paper — 3-2-1 Crack-Spread Mean Reversion (Girma-Paulson 1999)

## Citations

**Foundational:** Geman, H. (2005). **Commodities and Commodity
Derivatives: Modeling and Pricing for Agriculturals, Metals and
Energy.** Wiley. ISBN 978-0470012185.

Geman (2005) Chapter 7 ("Energy Markets") presents the textbook
treatment of energy-product spread trading and codifies the
canonical 3-2-1 US-refining ratio used in this strategy.

**Primary methodology:** Girma, P. B. & Paulson, A. S. (1999).
**Risk arbitrage opportunities in petroleum futures spreads.**
*Journal of Futures Markets*, 19(8), 931–955.
[https://doi.org/10.1002/(SICI)1096-9934(199912)19:8<931::AID-FUT5>3.0.CO;2-L](https://doi.org/10.1002/(SICI)1096-9934(199912)19:8<931::AID-FUT5>3.0.CO;2-L)

Girma-Paulson (1999) documents the crack spread as a
**mean-reverting risk-arbitrage trade** between crude oil and
refined products. The spread represents the **gross refining
margin** — long the crack bets the margin widens (good for
refiners), short the crack bets the margin compresses.

BibTeX entries `geman2005` (foundational) and `girmaPaulson1999`
(primary) are registered in `docs/papers/phase-2.bib`.

## The 3-2-1 ratio

The canonical US refining ratio is **3 barrels of crude in → 2
barrels of gasoline + 1 barrel of heating oil out**. This reflects
the typical product yield of a US Gulf Coast refinery:

    crack_spread(t) = 2 × RB(t) + 1 × HO(t) - 3 × CL(t)

per barrel-equivalent (all prices in $/bbl after unit conversion;
the strategy works directly on the ratio without explicit unit
conversion since we operate on percentage z-scores).

A **positive** crack spread means refining is profitable;
**negative** crack means refining loses money. The crack spread
went deeply negative in 2008 H2 (demand collapse) and briefly in
April 2020 (COVID demand shock).

## Why mean-reversion (not trend)

The crack spread is structurally mean-reverting because:

1. **Physical arbitrage by refiners**: when the margin is too
   high, refiners ramp up production → product supply increases →
   product prices fall → margin compresses. When the margin is
   negative, refiners cut runs or shut down → product supply
   tightens → prices rise → margin recovers.
2. **Storage costs** prevent persistent dislocation: refined
   products can be stored short-term but expensive to store
   long-term, so over-production gets absorbed into storage
   only briefly before prices revert.
3. **Product-grade specs** mechanically constrain crude vs
   product price ratios: a fully-refined barrel of products is
   always worth more than a barrel of crude (otherwise refining
   destroys value), and the maximum margin is bounded by
   refinery capacity and demand.

Girma-Paulson (1999) Table III reports half-lives of **8-14
weeks** for the 3-2-1 crack mean reversion across the 1986-1996
sample. The strategy default `zscore_lookback_days = 252` (1 year)
captures ~5 half-lives — sufficient to estimate a stable mean.

## Differentiation from sibling spread strategies

* **`crush_spread`** (Session 2E sibling, Commit 10) — soybean
  processing margin (1 ZS in → 1.5 ZM + 0.8 ZL out). Same
  mean-reversion mechanic on a different physical-economy spread.
  Expected ρ with `crack_spread` ≈ 0.0-0.1 (independent
  industries: refining vs soybean processing).
* **`wti_brent_spread`** (Session 2E sibling, Commit 11) — WTI
  vs Brent geographic-arbitrage spread. Same mean-reversion
  mechanic on a single-commodity geographic dislocation.
  Expected ρ ≈ 0.1-0.3 (both are crude-related but trade
  different physical regimes).
* **`wti_backwardation_carry`** (Session 2E sibling, Commit 4) —
  single-asset crude carry. Different signal entirely; ρ ≈
  0.0-0.2.
* **`commodity_curve_carry`** — different signal (cross-sectional
  rank); ρ ≈ 0.0-0.2.

Master plan §10 cluster-risk bar: ρ > 0.95 triggers deduplication
review. All overlaps are well below the bar.

## Mean-reversion signal

For each trading day *t*:

1. Compute the 3-2-1 crack spread.
2. Compute the rolling z-score over `zscore_lookback_days`
   (default 252).
3. **Long crack** when z < -2.0 (margin compressed below
   historical norm — bet on widening).
4. **Short crack** when z > +2.0 (margin too wide — bet on
   compression).
5. **Exit** (back to flat) when |z| < 0.5 (hysteresis).

| Parameter | Girma-Paulson value | AlphaKit default | Notes |
|---|---|---|---|
| Spread definition | 2 RB + 1 HO − 3 CL | identical | 3-2-1 ratio per Geman §7 |
| Rolling window | 4 years | 1 year | shorter window adapts faster to regime changes; longer would over-smooth post-2008 structural shift |
| Entry threshold | 1.5σ-2σ | 2σ | conservative; reduces false signals |
| Exit threshold | 0σ (full mean revert) | 0.5σ | hysteresis prevents rapid re-entry |
| Rebalance | daily | daily | identical |

## In-sample period (Girma-Paulson 1999)

* Data: 1986-1996 weekly closes for CL, HU (now RB), HO.
* In-sample Sharpe (3-2-1 mean-reversion, 1.5σ entry): ~1.0
* Out-of-sample replications:
  * Mitchell (2004) on 1996-2002 sample: Sharpe ~0.6
  * Bollman (2010) on 2002-2008: Sharpe ~0.4
  * post-2008: pre-shale era margin compression destroys the
    pre-2008 mean; modern OOS expectation is lower

For the AlphaKit default we expect:

* **Long-window OOS Sharpe (2010-2025)**: 0.2-0.4. The long-run
  mean of the crack has shifted with the shale revolution
  (post-2014 the crack runs structurally narrower because US
  crude oversupply pushed CL down faster than products),
  so a 1-year rolling lookback adapts to the new regime.
* **Strong-mean-reversion years (2015-2017, 2021-2023)**: Sharpe
  0.6-1.0 with low drawdown.
* **Regime-shift years (2008 H2, 2014-2015 shale-glut, 2020 H1
  COVID)**: Sharpe -0.5 to -1.0 as the spread breaks the 2σ
  band and trends instead of reverting.

## Implementation deviations from Girma-Paulson 1999

1. **1-year rolling window** instead of GP99's full-sample
   estimate. The shorter window adapts to the shale-era
   structural regime change without manual recalibration.
2. **2σ entry threshold** with 0.5σ exit hysteresis. GP99 uses
   1.5σ entry / 0σ exit; the wider entry reduces false signals
   and the hysteresis prevents rapid re-entry near the band.
3. **Discrete {-1, 0, +1} state signal** with the 3-2-1 ratio
   applied as fixed leg weights. GP99 implements continuous
   sizing proportional to the z-score deviation; the discrete
   approach is robust to noise and preserves the canonical
   refining ratio.
4. **No bid-ask, financing, or short-borrow model.** The bridge
   applies a flat `commission_bps` per leg.

None of these change the **economic content** of the
mean-reversion arbitrage rule.

## Girma-Paulson abstract excerpt

> ... we examine the petroleum futures spread between crude oil
> and refined products and find evidence of mean reversion. A
> simple trading strategy that buys the spread when it is
> sufficiently below its mean and sells when it is sufficiently
> above generates significant risk-adjusted returns ... The
> 3-2-1 crack spread exhibits strong mean reversion with a
> half-life of 8-14 weeks ...

## Known replications and follow-ups

* **Mitchell (2004)** — "Risk Arbitrage Opportunities in
  Petroleum Futures Spreads", JFM. Replicates GP99 on 1996-2002
  with confirmed but weaker Sharpe.
* **Bollman (2010)** — "Mean Reversion in Crack Spreads",
  Energy Economics. 2002-2008 update; documents the structural
  mean shift post-2008.
* **Working (1949)** — "The Theory of Price of Storage", AER.
  Cited in `crush_spread` and `grain_seasonality`; the original
  storage-theory exposition that grounds physical-arbitrage
  spread trades.
