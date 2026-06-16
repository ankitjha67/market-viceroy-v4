# Known failure modes — commodity_tsmom

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

Cross-commodity 12/1 time-series momentum on an 8-commodity default
panel. The strategy will lose money in the regimes below; none of
these are bugs, they are the cost of the trend-following risk
premium on commodities.

## 1. Trendless / range-bound commodity markets (2017, 2018)

In 2017-2018 most major commodities oscillated without establishing
durable trends. The TSMOM signal repeatedly entered long after a
brief rally only to be stopped out by a reversion (and the same for
shorts). CTA-style commodity sleeves (SG Trend, BTOP-50)
under-performed in 2018, with several posting Sharpe in the
**0 to −0.5** range.

Expected behaviour for `commodity_tsmom` in similar regimes:

* Sharpe of 0.0 to −0.5
* Drawdown of 8–15% from peak
* High monthly turnover (the multi-asset TSMOM book flips repeatedly)

## 2. Sharp regime changes (2008 GFC, 2014 oil collapse, 2020 March)

When commodity prices reverse sharply on macro shocks
(2008 commodity bubble burst, 2014 OPEC oil-price collapse, 2020
March COVID demand shock), the 12/1 signal lags by months. The
strategy holds the wrong position into the reversal and takes a
1-2 quarter drawdown before flipping.

Expected behaviour during sharp commodity reversals:

* Drawdown of 10-20% before the signal flips direction
* Recovery as the new trend establishes (typically 6-12 months
  post-reversal)

## 3. Single-asset blow-ups in the panel

Because each commodity gets its own signal, the strategy will
cheerfully scale into an asset that is trending into a bubble
(e.g. crude oil into H1 2008, natural gas into 2022 H1 before
the European energy crisis peaked). The trend flip comes late by
design — the cost of the 12/1 lookback — and the drawdown on the
bursting bubble is proportional to how late the flip is.

Mitigation: the per-asset leverage cap (`max_leverage_per_asset =
3.0`) prevents infinite weights when realised vol collapses, but
does not prevent regime-driven losses on a stretched single asset.

## 4. Cross-sectional dispersion collapse (2020 March)

When all commodities move in the same direction (universal
risk-off in 2020 March, broad reflation in 2021), the
cross-sectional dispersion shrinks and the long-short book becomes
a directional bet on the dominant trend. If the directional bet is
wrong, all 8 legs lose simultaneously.

Mitigation: pair the strategy with a market-regime filter (e.g.
exit when realised commodity index vol exceeds 2σ above its
long-run mean). Phase 3 candidate.

## 5. Asset-specific microstructure: continuous-contract roll bias

The default universe uses yfinance continuous-contract symbols
(``CL=F``, ``NG=F``, etc.). yfinance applies a back-adjustment that
preserves the close-to-close return on roll dates but introduces a
**level bias** in the historical series. The 12-month log return
computed on the back-adjusted series is approximately correct in
sign but mis-scales the absolute return at roll boundaries.

For real-feed Session 2H benchmarks, the cleanest path is to use
explicit per-contract data with a documented roll convention (e.g.
roll N days before expiry, hold front-month always). The
synthetic-fixture benchmark in this folder uses the
``generate_fixture_prices`` panel which is roll-bias-free.

## 6. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* `metals_momentum` (Session 2E sibling) — same mechanic, metals-
  only universe (GC, SI, HG, PL). Strong cluster — expected
  ρ ≈ 0.75-0.90 when metals dominate the broader commodity
  cross-section. Documented as cluster-risk acceptance: both
  strategies ship because the metals subset and the broader panel
  trade overlapping but not identical signals (commodity_tsmom
  includes energy + grains, metals_momentum is focused).
* Phase 1 `tsmom_12_1` (trend family) — same TSMOM mechanic on a
  6-asset balanced multi-asset universe (SPY/EFA/EEM/AGG/GLD/DBC).
  Overlap on GLD and DBC; expected ρ ≈ 0.6-0.8 in commodity-driven
  regimes (when commodities dominate the trend), lower otherwise.
* `commodity_curve_carry` (Session 2E sibling) — different signal
  (carry / roll yield) but trends and carry tend to align in
  steep-curve regimes; expected ρ ≈ 0.3-0.5.
* `bond_tsmom_12_1` (Session 2D rates family) — different asset
  class entirely; expected ρ ≈ 0.2-0.4.

These overlaps are expected. Phase 2 master plan §10 cluster-risk
acceptance bar: ρ > 0.95 triggers deduplication review. The
`metals_momentum` overlap (ρ ≈ 0.75-0.90) is borderline and will be
re-examined under the Session 2H real-feed benchmark.

## 7. Vol-target instability when realised vol is near zero

When a commodity's realised vol falls to near zero (e.g. ZW=F in
flat-grain regimes), `vol_target / realised_vol → ∞`. The leverage
cap (`max_leverage_per_asset = 3.0`) prevents this from blowing up
the backtest, but it does mean that a low-vol commodity contributes
a large weight to the gross book until vol reverts. Documented in
the strategy's edge-case docstring; mitigation is the leverage cap.

## Regime performance (reference, from public CTA commodity sleeves)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-crisis trending (2003-2007) | 2003-01 – 2007-06 | ~1.2 | −5% |
| Crisis (2008 GFC) | 2007-06 – 2009-06 | ~1.5 | −12% |
| Range-bound (2018) | 2018-01 – 2018-12 | ~−0.4 | −10% |
| Energy-crisis trend (2022 H1) | 2022-01 – 2022-06 | ~1.8 | −4% |
| Reversal (2023) | 2023-01 – 2023-12 | ~−0.5 | −9% |

(Reference ranges from public CTA commodity sleeves; the in-repo
benchmark is the authoritative source for this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
