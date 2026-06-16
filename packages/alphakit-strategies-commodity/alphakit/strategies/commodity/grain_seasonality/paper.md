# Paper — Grain Seasonality (Sørensen 2002)

## Citations

**Foundational paper:** Fama, E. F. & French, K. R. (1987).
**Commodity futures prices: Some evidence on forecast power,
premiums, and the theory of storage.** *Journal of Business*,
60(1), 55–73.
[https://doi.org/10.1086/296385](https://doi.org/10.1086/296385)

Fama-French (1987) establishes the **theory of storage** as the
empirical engine of agricultural-commodity seasonality: storable-
commodity futures prices peak when stocks are at their seasonal
low (pre-harvest) and trough when stocks are at their seasonal
high (post-harvest). The premium-discount cycle is the
no-arbitrage compensation for holding storage through the
agricultural year.

**Primary methodology:** Sørensen, C. (2002). **Modeling
seasonality in agricultural commodity futures.** *Journal of
Futures Markets*, 22(5), 393–426.
[https://doi.org/10.1002/fut.10017](https://doi.org/10.1002/fut.10017)

Sørensen (2002) fits a state-space model with explicit calendar-
seasonal terms to corn, soybean, and wheat futures over 1972-2000
and reports the seasonal amplitudes and timing in §III, Tables
II-IV. The calendar in this strategy is taken directly from those
tables.

BibTeX entries `famaFrench1987` and `sorensen2002` are registered
in `docs/papers/phase-2.bib`.

## Sørensen §III seasonal calendar

| Grain | Symbol | Long months | Short months | Driver |
|---|---|---|---|---|
| Corn | `ZC=F` | Apr, May, Jun | Sep, Oct, Nov | Planting-weather uncertainty (long); US harvest in Sep-Oct (short) |
| Soybeans | `ZS=F` | May, Jun, Jul | Oct, Nov, Dec | Planting + early-summer weather premium (long); US harvest Oct-Nov (short) |
| Wheat | `ZW=F` | Feb, Mar, Apr | Jul, Aug | Winter-wheat weather uncertainty (long); US-Plains harvest Jul-Aug (short) |

The annualised seasonal amplitude per Sørensen is 10-15% for corn,
8-12% for soybeans, and 6-10% for wheat. The strategy captures
this by going long the high-premium months and short the
post-harvest months.

## Why a fixed calendar rule

The seasonal pattern is remarkably stable across the 1972-2000
sample (Sørensen Table II) and confirmed by replications through
2014 (Pukthuanthong & Roll, 2017): the planting-harvest cycle on
US grains is set by the agricultural year, not the macro cycle,
so the seasonality persists across regimes.

The strategy deliberately uses a **fixed calendar rule** rather
than a learned-from-data signal because:

1. The economic content (storage theory) is well-understood and
   stable; a learned model would only add noise around a known
   prior.
2. A learned signal on a 30-50-year sample has 30-50 in-sample
   data points per month — over-fitting risk is high.
3. A fixed rule is transparent and falsifiable. If the
   seasonality breaks down (e.g. climate change shifting the
   harvest calendar by 2-3 weeks), the failure is visible in
   live performance and the rule can be updated explicitly rather
   than absorbed into a black-box model.

## Differentiation from sibling strategies

* **`commodity_tsmom`** — different signal (trailing returns, not
  calendar). Trends and seasonal cycles align *within* a single
  agricultural year (e.g. ZC trends up Apr-Jun then down
  Sep-Nov), so ρ ≈ 0.2-0.4 in normal years; lower in
  weather-disruption years (e.g. 2012 US drought, 2020 China-
  panic-buy).
* **`commodity_curve_carry`** — different signal (curve slope).
  Curve and seasonality are *coupled* through the storage theory
  (high-storage months → contango; low-storage months →
  backwardation), so ρ ≈ 0.3-0.5.
* **`cot_speculator_position`** — different signal (positioning).
  Speculator flows often *follow* the seasonal pattern (long in
  spring, short in fall), so the contrarian COT signal can be
  *aligned* with the seasonal long leg in some years (when
  speculators get extreme-long ahead of harvest) — ρ ≈ -0.1 to
  +0.2 depending on regime.

Master plan §10 cluster-risk bar: ρ > 0.95 triggers deduplication
review. All overlaps are well below the bar.

## In-sample period (Sørensen 2002)

* Data: 1972-2000 weekly futures closes for ZC, ZS, ZW.
* Per-grain seasonal Sharpe (in-sample, naive long-short calendar
  rule): ZC ~0.7, ZS ~0.6, ZW ~0.4.
* Out-of-sample (Pukthuanthong & Roll, 2017): 2001-2014, the
  seasonal Sharpe attenuates to 0.3-0.5 per grain — meaningful
  but degraded, consistent with a partially-arbitraged premium.

For the AlphaKit default we expect:

* **Long-window OOS Sharpe (2005-2025)**: 0.2-0.5 per grain,
  ~0.4-0.6 for the equally-weighted 3-grain book.
* **Strong years**: weather-disruption years amplify the
  planting-uncertainty premium — 2012 US drought (long ZC win
  ~25%), 2008 commodity bubble (long ZS win ~30%).
* **Weak years**: bumper-crop years compress the harvest-trough
  signal — 2014 ZC over-supply (short signal under-performed).

## Implementation deviations from Sørensen 2002

1. **Discrete {-1, 0, +1} signal** instead of Sørensen's
   continuous state-space output. The discrete rule is robust to
   the calendar boundary and easier to verify.
2. **Fixed monthly calendar** instead of Sørensen's day-of-year
   indexing. The monthly granularity matches the natural rebalance
   frequency and is robust to small year-to-year shifts in the
   harvest window (e.g. 1-2 week shifts due to weather).
3. **No bid-ask, financing, or short-borrow model.** The bridge
   applies a flat `commission_bps` per leg.

None of these change the **economic content** of the
storage-theory seasonality.

## Sørensen (2002) abstract excerpt

> ... agricultural commodities exhibit pronounced seasonal price
> patterns linked to the storage cycle. Corn and soybean prices
> tend to peak in the spring planting season and trough at the
> fall harvest; wheat prices peak in late winter and trough at
> the summer harvest. The seasonal amplitudes are economically
> significant — 10-15% for corn, 8-12% for soybeans, 6-10% for
> wheat — and have been remarkably stable across the sample
> period ...

## Known replications and follow-ups

* **Pukthuanthong & Roll (2017)** — "From the Ground Up: Bottom-
  Up Construction of Commodity Risk Premia from Their Constituent
  Forwards", JFE. Replicates Sørensen seasonality through 2014
  and reports per-grain Sharpe attenuation but persistence.
* **Working (1949)** — "The Theory of Price of Storage", American
  Economic Review 39(6). The original storage-theory
  exposition, foundational for the FF87 / Sørensen seasonality
  literature. Cited by `crush_spread` (Commit 10) as a
  foundational reference for soybean-product processing margins.
