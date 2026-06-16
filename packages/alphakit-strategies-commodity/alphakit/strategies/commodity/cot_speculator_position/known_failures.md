# Known failure modes — cot_speculator_position

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

Contrarian CFTC COT speculator-positioning trade. Long extreme-
short positioning, short extreme-long positioning, flat otherwise.
Failures cluster around regimes where (a) extreme positioning
*persists* longer than 3-6 months without reversal, (b) the COT
data is structurally re-classified by the CFTC, or (c) the
Friday-for-Tuesday lag is mis-applied.

## 1. Persistent-extreme-positioning regimes (2007-2008 crude bubble, 2010-2011 gold rally)

The contrarian COT rule assumes that extreme positioning reverts
within 3-6 months. In strong-trend regimes the extremes can
*persist* for a year or more:

* **2007-2008 crude bubble**: speculators were extreme-long crude
  through most of 2007 and H1 2008. The strategy was short
  through the entire bull leg and lost ~18-22% before crude
  finally reversed in July 2008.
* **2010-2011 gold rally**: speculators stayed in the top decile
  of net-long positioning for ~14 months. The strategy was short
  gold through most of the 2010-2011 rally and lost ~12-15%.
* **2014-2015 USD-strength reflation**: similar dynamic in
  agricultural shorts (ZC, ZS, ZW); speculators stayed extreme-
  short through a year of grain price collapse.

Expected behaviour for `cot_speculator_position` in
persistent-extreme regimes:

* Per-asset drawdown 10-25% over the persistent-extreme window
* Recovery typically takes 3-9 months after the trend finally
  reverses
* Sharpe over the event window highly negative; full-cycle Sharpe
  recovers to small positive

Mitigation: tighten the threshold to 95/5 instead of 90/10 to fade
*only* truly extreme positioning, accepting fewer signals. Or
overlay a trend filter (don't fade extreme-long if the trend is
still up, fade only on an early reversal signal).

## 2. CFTC data re-classifications (2009 Disaggregated Reports, 2020 Special Call)

The CFTC has periodically re-classified the COT data:

* **September 2009 Disaggregated COT**: split "non-commercial"
  into "managed money" and "other reportables"; split
  "commercial" into "producer/merchant" and "swap dealers". The
  legacy Combined Report continues but the structural composition
  of each bucket changed. Backtests using the Combined series
  through the transition show a discontinuity around Sep 2009.
* **2020 Special Call review** of swap-dealer classifications
  caused another structural shift in the commercial / swap-dealer
  split.

The strategy uses the **legacy Combined non-commercial / commercial
breakdown** for cross-period consistency. Users wanting the
post-2009 Disaggregated definitions should compute their own
positioning column and override the input convention.

## 3. Mis-applied Friday-for-Tuesday lag (most common failure mode)

If a backtest mistakenly uses the COT positioning *as of the
publication day* (Friday) without recognising it covers Tuesday's
positions, the resulting forward-looking bias produces ~3-5%
spurious annualised excess returns. This is the single most
common error in COT-strategy research.

This implementation enforces the lag via `cot_lag_days = 3` (the
Tuesday-to-Friday gap + 1-day execution buffer). Users running on
real CFTC data must align their ingestion to publish-Friday and
pre-lag the data so the synthetic shift here matches the live
timeline; otherwise the lag is double-applied and the signal is
under-powered.

## 4. Quiet-positioning periods (2014 Aug-Oct, 2017 Q1)

When speculator positioning hovers around the historical median
(percentile 30-70) for an extended period, the strategy stays
flat across all legs. This is *not* a loss — but the opportunity
cost relative to a curve-carry or trend-following strategy is
high. Approximately 60-70% of trading days fall in this
quiet-positioning regime; the strategy generates signals only on
the remaining 30-40%.

Users wanting full-period exposure should pair this with
`commodity_curve_carry` (which is active in all curve regimes)
or `commodity_tsmom` (which is active in all trend regimes).

## 5. Single-asset position-shift events

Specific re-classification or large-account exit events can shift
a single commodity's positioning out of historical-typical range:

* **2014 Q4 oil supermajor de-leverage** caused a one-time crude
  COT positioning shift that produced a fake "extreme-long" signal
  ~3 months after the event.
* **2018 Q1 corn fund liquidation** (managed-money exit) produced
  a fake "extreme-short" signal that was reversed within 8 weeks.

These events do not reverse mean: the percentile metric is
robust to single shocks but the strategy will trade the false
signal for ~4-12 weeks before the rolling lookback re-baselines.
Per-asset drawdown 4-7% per event.

## 6. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **`commodity_curve_carry`** (Session 2E sibling, Commit 6) —
  different signal dimension (curve slope, not positioning).
  Expected ρ ≈ 0.0-0.2 — essentially uncorrelated except in
  rare regimes where extreme curve slope and extreme positioning
  both fire.
* **`wti_backwardation_carry`** / **`ng_contango_short`** — same
  reasoning. Different signal dimension; ρ ≈ 0.0-0.2.
* **`commodity_tsmom`** (Session 2E sibling) — momentum signal
  is *the same direction* as positioning during trend-following
  CTA inflows (when speculators are crowding into the trend, the
  COT signal goes contrarian against the momentum signal).
  Expected ρ ≈ -0.2 to 0.0 (mildly *negative* in trending
  regimes).
* **Phase 1 `tsmom_12_1`** (trend family) — same reasoning;
  expected ρ ≈ -0.2 to 0.0.

The mild *negative* correlation with the trend / momentum
strategies is by construction — extreme positioning is a
contrarian fade against crowded trends. The two signal types
diversify cleanly.

## 7. CFTC publication outages (rare but documented)

CFTC publication can be delayed by federal-government shutdowns
(e.g. October 2013 — 16-day gap; January 2019 — 35-day gap). The
strategy interprets stale data as "no new signal" and stays in
the prior-week position through the outage. On long outages this
can produce 2-5% drag from holding stale positions through
intervening market moves. This is a data-quality known failure;
users running real CFTC data should overlay a data-staleness
filter (e.g. exit positions if data is > 14 days old).

## Regime performance (reference, from public CTA COT sleeves)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-bubble normal | 2003-2006 | ~0.7 | −5% |
| Bubble + persistent-extreme | 2007-2008 H1 | ~−1.5 | −22% |
| Crisis + reversal | 2008-09 – 2009-09 | ~1.0 | −7% |
| Gold rally persistent-extreme | 2010-2011 | ~−0.8 | −15% |
| Post-rally reversal | 2012-2013 | ~0.9 | −6% |
| Quiet-positioning | 2014 H2 | ~0.0 (flat) | 0% |
| Post-COVID re-extremes | 2021-2023 | ~0.6 | −9% |

(Reference ranges from public CTA COT sleeves; the in-repo
benchmark is the authoritative source for this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
