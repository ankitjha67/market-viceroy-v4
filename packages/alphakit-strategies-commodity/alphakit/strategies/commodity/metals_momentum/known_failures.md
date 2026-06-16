# Known failure modes — metals_momentum

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

Metals-only 12/1 time-series momentum on a 4-metal default panel
(GC, SI, HG, PL). The strategy will lose money in the regimes
below; none of these are bugs, they are the cost of the
trend-following risk premium on a narrow sub-panel.

## 1. Range-bound metals regimes (gold 2013-2018, copper 2014-2016)

Gold ran sideways from late 2013 to early 2019; copper traded a
narrow range from 2014 to mid-2016. In both windows, the 12/1
signal flipped repeatedly without finding a durable trend, and
several gold-focused CTAs posted **0 to −0.4 Sharpe** over the same
period.

Expected behaviour for `metals_momentum` in similar regimes:

* Sharpe of 0.0 to −0.4
* Drawdown of 5–12% from peak
* Elevated turnover (monthly flips on every leg)

## 2. Sharp metals reversals (2008 GFC, 2013 gold flash crash, 2020 silver squeeze)

Metals are particularly prone to volatility-spike reversals on
macro shocks: the 2008 GFC saw gold and silver round-trip 30%+
inside two quarters; April 2013 saw a 13% one-day gold drop on
ETF-position liquidations; January 2021 saw the silver squeeze
(+15% intra-week, then full mean-reversion). The 12/1 signal lags
each of these by months and the strategy holds the wrong direction
into the reversal.

Expected behaviour during sharp metals reversals:

* Drawdown of 8-15% before the signal flips direction
* Recovery as the new trend establishes (typically 6-12 months
  post-reversal)

## 3. Industrial-vs-monetary divergence (2021-2022)

Through 2021-2022 copper sold off on China-demand fears while gold
rallied on real-rate suppression and central-bank buying. The
4-metal book's gross exposure stayed flat (long monetary, short
industrial) but the legs decorrelated and dispersion volatility
spiked. The strategy is **not** designed to exploit this
divergence — it is per-asset, not cross-sectional rank — so it
neither benefits from nor is hurt by sub-cluster decoupling.
Documented here so users do not expect cross-sectional alpha.

## 4. Single-asset blow-ups in the panel

The strategy will cheerfully scale into a metal that is trending
into a bubble (e.g. silver into early 2011, copper into 2008 H1,
nickel into 2022 H1 — though nickel is not in the default
universe). The trend flip comes late by design — the cost of the
12/1 lookback — and the drawdown on the bursting bubble is
proportional to how late the flip is.

Mitigation: the per-asset leverage cap (`max_leverage_per_asset =
3.0`) prevents infinite weights when realised vol collapses, but
does not prevent regime-driven losses on a stretched single metal.

## 5. Asset-specific microstructure: continuous-contract roll bias

The default universe uses yfinance continuous-contract symbols
(`GC=F`, `SI=F`, `HG=F`, `PL=F`). yfinance applies a
back-adjustment that preserves the close-to-close return on roll
dates but introduces a **level bias** in the historical series.
Metals contracts roll quarterly (Mar/Jun/Sep/Dec) and the
back-adjustment can mis-scale absolute returns at roll boundaries.
The 12-month log return is approximately correct in *sign* but the
absolute return at roll boundaries can be off by 1-3%.

For real-feed Session 2H benchmarks the cleanest path is to use
explicit per-contract data with a documented roll convention. The
synthetic-fixture benchmark in this folder is roll-bias-free.

## 6. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **`commodity_tsmom`** (Session 2E sibling) — same mechanic on
  the broader 8-commodity panel. **Strong cluster** — expected
  ρ ≈ 0.75-0.90 when metals dominate the broader commodity
  cross-section. Documented as cluster-risk acceptance: both
  strategies ship because the metals subset and the broader panel
  trade overlapping but not identical signals (commodity_tsmom
  includes energy + grains, metals_momentum is the sub-cluster
  isolation users explicitly want when they want metals beta
  without energy/grains).

  Master plan §10 cluster-risk bar: ρ > 0.95 triggers
  deduplication review. The predicted ρ ≈ 0.75-0.90 is borderline
  and will be re-examined under the Session 2H real-feed
  benchmark; if the realised overlap exceeds 0.95 we will
  re-evaluate whether metals_momentum continues to ship as a
  separate strategy or is merged into commodity_tsmom as a
  configuration (`universe = metals_only`).
* **Phase 1 `tsmom_12_1`** (trend family) — same TSMOM mechanic on
  a balanced 6-asset multi-asset universe (SPY/EFA/EEM/AGG/GLD/DBC).
  Overlap via GLD only; expected ρ ≈ 0.3-0.5 in metals-driven
  regimes, lower otherwise.
* **`commodity_curve_carry`** (Session 2E sibling) — different
  signal (carry / roll yield) on the broader panel; expected
  ρ ≈ 0.2-0.4 (metals carry differs from grains carry).
* **`bond_tsmom_12_1`** (Session 2D rates family) — different
  asset class entirely; expected ρ ≈ 0.1-0.3.

## 7. Vol-target instability when realised vol is near zero

When a metal's realised vol falls to near zero (e.g. flat-period
gold in mid-2013), `vol_target / realised_vol → ∞`. The leverage
cap (`max_leverage_per_asset = 3.0`) prevents this from blowing up
the backtest, but it does mean that a low-vol metal contributes a
large weight to the gross book until vol reverts. Documented in
the strategy's edge-case docstring; mitigation is the leverage
cap.

## 8. Narrow-universe penalty vs commodity_tsmom

The 4-metal default produces a smaller cross-sectional dispersion
than the 8-commodity broader panel. In multi-asset trending
regimes this strategy will under-perform `commodity_tsmom` by
0.1-0.2 Sharpe simply because the panel is narrower. Users wanting
broader commodity TSMOM should prefer `commodity_tsmom`; users
wanting metals-only beta should prefer this strategy. Both are
shipped to make the choice explicit.

## Regime performance (reference, from public CTA metals sleeves)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Gold bull-trend | 2003-01 – 2011-09 | ~0.8 | −9% |
| Range-bound gold | 2013-04 – 2018-12 | ~−0.3 | −12% |
| Copper supply shock | 2020-04 – 2022-03 | ~1.1 | −7% |
| Silver squeeze + reversion | 2021-01 – 2021-06 | ~−0.5 | −10% |
| Reflation + central-bank gold buying | 2023-10 – 2024-12 | ~1.0 | −5% |

(Reference ranges from public CTA metals sleeves; the in-repo
benchmark is the authoritative source for this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
