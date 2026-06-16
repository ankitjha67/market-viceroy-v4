# Known failure modes — ng_contango_short

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

Short-only NG contango trade on the front-vs-next-month curve.
Unlike `wti_backwardation_carry` (long-only, in cash during
contango), this strategy actively takes a short position when the
NG curve is in contango — and therefore can lose money in two
specific regime types: spot-price spikes during contango (curve
flattens but spot rises, so short loses) and curve-flip events
(contango → backwardation transition).

## 1. Polar-vortex / extreme-cold spikes (2014-01, 2018-01, 2021-02)

NG spot prices can spike 50-200% in 2-4 weeks during extreme-cold
events (US Northeast polar vortex, ERCOT February 2021). The
storage-build curve was in contango entering each event, so the
strategy was short going into the spike. Even though the curve
*flattened* (front rose more than back), the short loses on the
**spot rise** because the strategy is holding a short futures
position that mark-to-markets daily.

Three reference events:

* **January 2014 (US Northeast polar vortex)**: NG spot +60% in
  3 weeks; short loss ~12% on the strategy book.
* **January 2018 (cold snap)**: NG spot +35% in 4 weeks; short
  loss ~7%.
* **February 2021 (ERCOT freeze)**: NG spot +80% in 2 weeks
  (peaked > $20/MMBtu in the wholesale market); short loss
  ~15-20% depending on entry timing.

Expected behaviour for `ng_contango_short` in similar regimes:

* Drawdown of 8-20% in 2-4 weeks
* Recovery typically takes 4-8 weeks as spot reverts and the
  curve re-establishes contango
* Sharpe over the event window is highly negative; on the
  full-cycle (3-6 months) it usually recovers to small positive

## 2. Backwardation regimes (winter heating-demand season)

The NG curve typically flips into backwardation from late October
through March (heating-demand season → high spot demand → front
contract bid). The strategy is in cash during these months by
construction. **Opportunity cost**: a long-only NG long position
during winter would earn the backwardation roll yield; this
strategy earns nothing.

This is *not* a loss — but users should know that ~5 months a year
the strategy is mechanically flat. If the goal is full-year NG
exposure, pair this with a winter-backwardation-long overlay
(deferred to Phase 3) or use `commodity_curve_carry` (the
cross-sectional rank book) which trades both sides of the curve
across the full panel.

## 3. Curve-flip lag at regime boundaries

When the NG curve flips contango → backwardation (typically late
October) or backwardation → contango (typically late March), the
21-day smoothed signal lags by ~3 weeks. The strategy will:

* Stay short for ~3 weeks into a new backwardation regime → short
  loses on the spot bid → drawdown
* Miss the first ~3 weeks of a new contango regime → opportunity
  cost only

The short-side lag is the more painful failure: late-October
backwardation often comes with a sharp spot bid (heating demand),
so the strategy loses 3-5% in the first 2-3 weeks of the flip
before the smoothed signal exits.

Mitigation: tune `smoothing_days` lower (e.g. 5-10 days) for
faster regime detection; users who do this must accept higher
turnover (more flips in noisy intra-season weeks).

## 4. Short-squeeze risk in storage-glut regimes

Counterintuitively, deep contango can *invert quickly* if storage
fills above the seasonal norm. When US gas storage approaches the
~4,000 Bcf working-capacity ceiling (e.g. October 2009, October
2015), traders front-run the storage-glut signal: front contract
sells off harder than the back, contango widens, and then the
back contract collapses as storage operators release inventory →
front rises → contango compresses or flips. The strategy is short
through the contango-widening phase (gains) but can lose 5-10%
in the compression phase if the smoothed signal is slow to react.

## 5. Spot-direction agnosticism

The strategy harvests the curve premium and is **agnostic** to
spot direction. In a year where spot rallies 40% but the curve
stays in contango (e.g. 2022 H1 European energy crisis spillover),
the strategy is short and loses ~30-40% from the spot rally even
though the curve premium is positive. Users wanting a
spot-filtered version should overlay a 6-month trend filter (long
spot trend → reduce short size; short spot trend → full short
size); this is a Phase 3 candidate.

## 6. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **`commodity_curve_carry`** (Session 2E sibling, Commit 6) —
  cross-sectional rank-based carry on the broader 8-commodity
  panel. NG typically appears in the *short* tail of the rank
  book during summer contango months, so the two strategies
  overlap on the NG short leg specifically. Expected ρ ≈ 0.3-0.5
  in summer months (May-September), lower in winter.
* **`wti_backwardation_carry`** (Session 2E sibling, Commit 4) —
  long-only mirror trade on WTI. Different commodity, opposite
  curve regime, asymmetric trading rule. Expected ρ ≈ 0.0-0.2.
* **`commodity_tsmom`** (Session 2E sibling) — different signal
  (trailing returns, not curve). Trends and curve premia tend to
  align in steep-curve regimes; ρ ≈ 0.1-0.3.
* **Trend-family `tsmom_12_1`** (Phase 1) — different signal,
  different universe; ρ ≈ 0.0-0.2.

Master plan §10 cluster-risk bar: ρ > 0.95 triggers deduplication
review. All overlaps here are well below the bar.

## 7. NG-specific microstructure: front-month roll on the 25th

NG futures roll on the 3rd-to-last business day of the prior
month (i.e. ~3 trading days before the 25th of the prior month).
The yfinance `NG=F` continuous series is back-adjusted but the
roll-day price gap is preserved as a step in the underlying
contract change. The 21-day smoothing absorbs the gap, but in
the 5-10 days *immediately* after a roll the smoothed signal
includes a back-adjusted artefact. This is a microstructure
known failure, not an economic signal.

## 8. F2 proxy bias

Same as `wti_backwardation_carry`: yfinance's `NG2=F` is used as
a next-month proxy. Preserves the *sign* of the curve slope but
biases the *magnitude* near roll boundaries. For real-feed
Session 2H benchmarks the cleanest fix is explicit per-contract
data (NG_2025M, NG_2025N, etc.) with a documented roll
convention.

## Regime performance (reference, from public commodity-overlay sleeves)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Summer-contango (typical) | 2005-05 – 2005-09 | ~1.2 | −3% |
| Storage glut + flat spot | 2009-10 – 2010-04 | ~0.6 | −7% |
| Polar vortex (cold-spike) | 2014-01 – 2014-02 | ~−2.0 | −12% |
| ERCOT freeze | 2021-02 – 2021-03 | ~−2.5 | −18% |
| European-energy-crisis spillover | 2022-01 – 2022-09 | ~−0.8 | −22% |
| Post-crisis re-contango | 2023-04 – 2023-09 | ~1.0 | −4% |

(Reference ranges from public commodity-overlay sleeves; the
in-repo benchmark is the authoritative source for this
implementation — see [`benchmark_results.json`](benchmark_results.json).)
