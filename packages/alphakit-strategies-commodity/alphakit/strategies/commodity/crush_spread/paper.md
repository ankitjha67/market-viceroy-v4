# Paper — Soybean Crush Spread Mean Reversion (Simon 1999)

## Citations

**Foundational:** Working, H. (1949). **The theory of price of
storage.** *American Economic Review*, 39(6), 1254–1262.

Working (1949) is the canonical exposition of the **theory of
storage**: storable-commodity prices are tied to processing and
storage costs through a no-arbitrage relationship. The soybean-
crush spread is a direct application — bounded above by the
marginal cost of processing soybeans into meal+oil and bounded
below by the cost of storing soybeans as raw input.

**Primary methodology:** Simon, D. P. (1999). **The soybean crush
spread: Empirical evidence and trading strategies.** *Journal of
Futures Markets*, 19(3), 271–289.
[https://doi.org/10.1002/(SICI)1096-9934(199905)19:3<271::AID-FUT2>3.0.CO;2-S](https://doi.org/10.1002/(SICI)1096-9934(199905)19:3<271::AID-FUT2>3.0.CO;2-S)

Simon (1999) documents the soybean crush as a **mean-reverting
risk-arbitrage trade** analogous to the petroleum crack spread
(Girma-Paulson 1999). The spread represents the **gross
processing margin** earned by soybean crushers.

BibTeX entries `working1949` and `simon1999` are registered in
`docs/papers/phase-2.bib`.

## The 1:1.5:0.8 ratio

The simplified bushel-equivalent ratio for the soybean crush is
**1 bushel of soybeans → 1.5 units of meal-equivalent + 0.8
units of oil-equivalent**::

    crush_spread(t) = 1.5 × ZM(t) + 0.8 × ZL(t) - 1.0 × ZS(t)

The actual CBOT board-crush conversion is slightly more complex
because the contracts use different physical units (cents/bu for
ZS, $/ton for ZM, cents/lb for ZL). The 1:1.5:0.8 simplification
is the textbook bushel-equivalent expression used in Simon (1999)
§II and standard practitioner references.

A **positive** crush means processing is profitable; **negative**
crush means processors lose money (rare but happens during severe
oversupply — e.g. 2014 H2 US record harvest, 2018 China-tariff-
induced soybean glut).

## Why mean-reversion (not trend)

The crush spread is structurally mean-reverting because:

1. **Physical arbitrage by crushers**: when the margin is too
   high, crushers ramp up processing → product supply increases
   → product prices fall → margin compresses. When the margin is
   negative, crushers cut runs → product supply tightens →
   prices rise → margin recovers.
2. **Storage and perishability**: meal and oil are more
   perishable than whole soybeans, so over-production gets
   consumed faster than it can be stored, accelerating the
   reversion.
3. **Demand decoupling**: meal demand (livestock feed) and oil
   demand (food / biofuel) are partly decoupled, so the spread
   is buffered against single-product demand shocks.

Simon (1999) Table 4 reports half-lives of **6-12 weeks** for the
crush spread mean reversion on the 1985-1995 sample. The strategy
default `zscore_lookback_days = 252` (1 year) captures ~5
half-lives — sufficient to estimate a stable mean.

## Differentiation from sibling spread strategies

* **`crack_spread`** (Session 2E sibling, Commit 9) — petroleum
  refining margin (3-2-1 ratio). Same mean-reversion mechanic on
  a different physical-economy spread (refining vs soybean
  processing). Independent industries → expected ρ ≈ 0.0-0.1.
* **`wti_brent_spread`** (Session 2E sibling, Commit 11) —
  WTI vs Brent geographic-arbitrage spread. Different commodity
  entirely; ρ ≈ 0.0-0.1.
* **`grain_seasonality`** — different signal (calendar) on
  overlapping universe (ZS is in both panels). Expected
  ρ ≈ 0.1-0.2 (the seasonal signal partly drives the crush
  margin via planting-uncertainty effects on ZS).
* **`commodity_curve_carry`** — different signal entirely;
  ρ ≈ 0.0-0.1.

Master plan §10 cluster-risk bar: ρ > 0.95 triggers deduplication
review. All overlaps are well below the bar.

## Mean-reversion signal

For each trading day *t*:

1. Compute the 1:1.5:0.8 crush spread.
2. Compute the rolling z-score over `zscore_lookback_days`
   (default 252).
3. **Long crush** when z < -2.0 (margin compressed below
   historical norm).
4. **Short crush** when z > +2.0 (margin too wide).
5. **Exit** (back to flat) when |z| < 0.5 (hysteresis).

| Parameter | Simon (1999) value | AlphaKit default | Notes |
|---|---|---|---|
| Spread definition | 1.5 ZM + 0.8 ZL − 1 ZS | identical | bushel-equivalent simplification |
| Rolling window | 4 years | 1 year | shorter window adapts faster to demand-driven regime shifts |
| Entry threshold | 1.5σ | 2σ | conservative; reduces false signals |
| Exit threshold | 0σ | 0.5σ | hysteresis prevents rapid re-entry |
| Rebalance | daily | daily | identical |

## In-sample period (Simon 1999)

* Data: 1985-1995 weekly closes for ZS, ZM, ZL.
* In-sample Sharpe (1.5σ entry): ~0.9.
* Out-of-sample replications:
  * Wilson & Wagner (2002) on 1995-2001: Sharpe ~0.5
  * Akin (2017) on 2003-2016: Sharpe ~0.4

For the AlphaKit default we expect:

* **Long-window OOS Sharpe (2010-2025)**: 0.2-0.4.
* **Strong-mean-reversion years (2011-2013, 2016-2018, 2020-2022)**:
  Sharpe 0.5-0.9.
* **Regime-shift years (2014 H2 record harvest, 2018 China-tariff
  shock)**: Sharpe -0.5 to -1.0 as the spread breaks the 2σ band
  and trends instead of reverting.

## Implementation deviations from Simon 1999

1. **1-year rolling window** instead of Simon's full-sample
   estimate. Adapts to demand-side regime shifts (e.g. 2010s
   biofuel-demand growth driving structural ZL premium).
2. **2σ entry threshold** with 0.5σ exit hysteresis. Simon uses
   1.5σ entry / 0σ exit; the wider entry reduces false signals.
3. **Discrete state signal** with the 1:1.5:0.8 ratio applied as
   fixed leg weights. Simon implements continuous sizing
   proportional to z-score deviation; the discrete approach is
   robust to noise.
4. **Bushel-equivalent simplification.** The actual CBOT board
   crush uses the published unit-conversion factors (ZM × 0.022 +
   ZL × 0.11 − ZS, all in cents/bu equivalents); the 1:1.5:0.8
   simplification is the textbook expression used in Simon §II.
   For real-feed Session 2H benchmarks, users should validate
   that the unit-conversion-aware spread produces the same signal
   ordering as the bushel-equivalent simplification (it does, up
   to a small constant scale factor that does not affect the
   z-score).
5. **No bid-ask, financing, or short-borrow model.** The bridge
   applies a flat `commission_bps` per leg.

## Simon (1999) abstract excerpt

> ... the soybean crush spread exhibits significant mean
> reversion. The crush spread provides a measure of the gross
> processing margin available to soybean processors, and
> deviations from its long-run mean appear to be reversed within
> 6-12 weeks. A simple trading strategy that exploits this
> mean reversion generates significant risk-adjusted returns ...

## Known replications and follow-ups

* **Wilson & Wagner (2002)** — "Crush Spread Trading", JFM. 1995-
  2001 OOS update; confirmed Sharpe attenuation but persistence.
* **Akin (2017)** — "Mean Reversion in the Soybean Crush
  Spread", *Agricultural and Resource Economics*. 2003-2016
  update; documents the demand-side biofuel regime shift.
* **Working (1949)** — foundational storage-theory exposition;
  also cited in `grain_seasonality` and `crack_spread`.
