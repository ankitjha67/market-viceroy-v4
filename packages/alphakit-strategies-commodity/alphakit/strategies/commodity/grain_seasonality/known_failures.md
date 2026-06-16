# Known failure modes — grain_seasonality

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

Calendar-based seasonal trade on US grain futures (ZC, ZS, ZW).
The strategy follows a fixed monthly calendar; failures cluster
around regimes where the **agricultural calendar is disrupted**
or where **macro shocks override the seasonal signal**.

## 1. Bumper-crop years (2014, 2017 ZC; 2018 ZS)

When US weather is consistently favourable, the planting-
uncertainty premium fails to materialise (no scare → no premium →
long signal under-performs) **and** the harvest-trough is amplified
by oversupply (good for the short signal but the magnitude is
larger than the calendar predicts).

Net effect: long leg loses ~5-10%, short leg wins ~5-10%; the
long-short book's Sharpe is moderate (~0.2-0.4) but with high
intra-year volatility.

## 2. Weather-disruption years (2012 US drought, 2020 China-panic)

Conversely, weather-disruption years amplify the planting-
uncertainty premium dramatically:

* **2012 US drought**: corn yields collapsed 25% from trend; ZC
  rallied from $5.50 to $8.50 over Apr-Aug. The seasonal long
  signal (Apr-Jun) won ~20-25%; the seasonal short signal
  (Sep-Nov) lost ~5-8% as drought-supply concerns persisted into
  harvest.
* **2020 H2 China panic-buying**: ZS rallied from $9 to $13 over
  Aug-Dec on China demand surge. The seasonal short signal
  (Oct-Dec) lost ~15-20%.
* **2022 H1 Ukraine grain-export disruption**: ZW spiked 60% in
  Q1 2022. The seasonal long signal (Feb-Apr) won ~40%; the
  short signal (Jul-Aug) was overridden by the persistent
  ex-Ukraine demand premium and lost ~10%.

Expected behaviour in weather-disruption years:

* Long leg: outsized gains (+15-30% per leg)
* Short leg: outsized losses (-10-20% per leg)
* Net Sharpe over the disruption year: variable; can be very
  positive (2012 ZC) or very negative (2020 ZS, 2022 ZW)

## 3. Non-US grain dynamics (post-2010)

The seasonal calendar is calibrated to **US** grain markets.
Post-2010, China and Brazil have become significant grains
producers/consumers and the US-only calendar has progressively
weakened:

* Brazilian soybean harvest is February-April (opposite to US
  Oct-Nov harvest), so global-soy supply now has a March trough
  instead of a single October trough. The Sørensen calendar
  short window (Oct-Dec) catches half of the global cycle and
  misses the March trough.
* Chinese demand is concentrated in Oct-Dec for ZS (post-US
  harvest stockpiling) which can override the post-harvest short
  signal (as in 2020).

Mitigation: in Phase 3 the calendar will be updated to reflect
the global production cycle (e.g. add a March short window for
ZS to capture the Brazilian harvest); for now, users running real
data should be aware of the geographic concentration risk.

## 4. Climate-change calendar drift (subtle, multi-year)

US grain harvest dates have shifted by 1-2 weeks over the past
20 years due to climate change (earlier last-frost dates extend
the growing season). The fixed monthly calendar is robust to
1-2 week drift but not to larger shifts. Users should periodically
re-validate the calendar against USDA NASS harvest progress
reports.

## 5. Short-side asymmetry near zero-bound

Grain futures cannot trade below zero (unlike crude in 2020). If
a grain hits the exchange-imposed daily limit (typically 30¢/bu
for ZC), the short side cannot be marked in the usual way and
the strategy's signal is technically valid but the realised
return diverges from the close-to-close spec.

This has happened ~5 times in the past 20 years (notably ZC
limit-down days during the 2008 unwind and the 2012 drought
unwind in Aug-Sep).

## 6. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **`commodity_tsmom`** — trends within a single agricultural
  year tend to align with the seasonal pattern. Expected
  ρ ≈ 0.2-0.4 in normal years, lower in weather-disruption
  years.
* **`commodity_curve_carry`** — curve and seasonality are
  *coupled* through the storage theory (high-storage months →
  contango; low-storage months → backwardation). Expected
  ρ ≈ 0.3-0.5.
* **`cot_speculator_position`** — speculator flows often follow
  the seasonal pattern; the contrarian COT signal can be aligned
  with the seasonal long leg in extreme years. Expected
  ρ ≈ -0.1 to +0.2.
* **Phase 1 `tsmom_12_1`** (trend family) — different universe
  (no grains in the 6-ETF panel); ρ ≈ 0.0-0.1.

All overlaps below the master plan §10 deduplication bar (ρ > 0.95).

## 7. Calendar-rule rigidity

By design, the strategy emits *exactly the same signal* every year
on the same calendar dates. In high-conviction adverse regimes
(e.g. mid-2022 European-energy-crisis spillover into grains) the
strategy cannot update its prior — it follows the calendar
mechanically. Users who want adaptive seasonality should overlay
a regime filter (e.g. exit positions if the YTD return on the
relevant grain is > +30% or < -30%); this is a Phase 3 candidate.

## 8. Single-grain blow-up exposure

The strategy holds 3 grains (ZC, ZS, ZW) equally. A single-grain
blow-up — e.g. ZW Q1 2022 Ukraine spike — can cause the
corresponding leg to lose 15-25% in a quarter. With equal
weighting, the contribution to portfolio drawdown is ~5-8%. Users
worried about this should restrict the universe (e.g. drop ZW for
periods of geopolitical tension) or scale per-leg by realised
vol.

## Regime performance (reference, from public CTA seasonality sleeves)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Normal seasonal | 2003-2007 | ~0.6 | −5% |
| 2008 commodity bubble | 2007-12 – 2008-08 | ~1.4 | −4% |
| Bumper-crop / oversupply | 2014 | ~0.2 | −7% |
| 2012 US drought | 2012-04 – 2012-12 | ~1.0 (with offsetting short loss) | −9% |
| 2020 China-panic | 2020-08 – 2020-12 | ~−0.8 | −12% |
| 2022 Ukraine spike | 2022-02 – 2022-08 | ~−0.4 (Q1 long win, Q3 short loss) | −10% |

(Reference ranges from public CTA seasonality sleeves; the
in-repo benchmark is the authoritative source for this
implementation — see [`benchmark_results.json`](benchmark_results.json).)
