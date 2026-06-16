# Paper — G10 Cross-Country Sovereign Bond Carry (Asness §V, 2013)

## Citation

**Primary methodology:** Asness, C. S., Moskowitz, T. J. & Pedersen,
L. H. (2013). **Value and momentum everywhere.** *Journal of
Finance*, 68(3), 929–985.
[https://doi.org/10.1111/jofi.12021](https://doi.org/10.1111/jofi.12021)

Section V documents both *time-series* and *cross-sectional* carry
on sovereign bonds across G10 markets. The cross-sectional bond
carry sleeve ranks countries by their bond carry (yield level minus
short-rate, equivalently the trailing return on a constant-maturity
bond) and goes long the top quantile / short the bottom.

BibTeX entry: `asness2013value` (already in `docs/papers/phase-2.bib`,
added by `bond_tsmom_12_1` in Commit 2).

## Why a single primary citation

Asness §V specifies the cross-sectional carry rule directly. KMPV
(2018) generalises the carry definition across asset classes, but
for the *bond* sleeve the methodology is identical. We anchor on
Asness 2013 because it is the simpler bond-specific reference
without the cross-asset-class generalisation.

## Differentiation from sibling carry strategies

* **`bond_carry_roll`** (Phase 1 carry family) — cross-sectional
  carry on a *US-centric* bond panel (multiple US bond indices).
  Uses the same trailing-return-as-carry-proxy mechanic, but the
  universe is US-only.
* **`g10_bond_carry`** (this strategy) — *G10-cross-country*
  version. Same mechanic, different universe. The two strategies
  trade orthogonal information (US-only dispersion vs G10
  cross-country dispersion) and are both shipped as part of
  Phase 2.
* **`bond_carry_rolldown`** (rates family, Commit 6) — *time-series*
  duration overlay on a single bond conditional on the slope.
  Different signal type entirely.

The trio (`bond_carry_roll`, `g10_bond_carry`, `bond_carry_rolldown`)
spans US-cross-section, G10-cross-section and US-time-series carry
respectively.

## Algorithm

For each month-end ``t`` and bond panel of ``N`` country bond
proxies:

1. **Carry proxy:** trailing ``lookback_months``-month log return.
2. **Optional duration normalisation:** if ``durations`` is
   provided, divide each country's carry proxy by its modified
   duration before ranking.
3. **Cross-sectional rank** of the carry proxy across countries.
4. **Dollar-neutral weights** via the demeaned-rank construction.
5. **Forward-fill** monthly weights to daily.

| Parameter | Default | Notes |
|---|---|---|
| `lookback_months` | `3` | Asness §V uses a short window |
| `durations` | `None` | optional per-country duration map |

## Currency-hedging caveat

G10 cross-country bond carry returns can be either *unhedged* (in
local currency, exposes to FX) or *FX-hedged* (the canonical
AMP 2013 §V version). This implementation operates on whatever
bond price series are passed in:

* Unhedged USD-denominated ETF (e.g. BWX) — strategy includes
  implicit FX exposure.
* FX-hedged USD-equivalent series (constructed via FX forwards) —
  strategy isolates pure rate carry per the paper.

Real-feed Session 2H benchmarks should construct the FX-hedged
return series for fidelity. The fixture-based benchmark in this
folder uses US-only bond ETFs as a fallback, which entirely
sidesteps the FX question — see `known_failures.md` for the
synthetic-vs-real gap discussion.

## Per-country duration normalisation

Different countries have materially different sovereign-bond
duration profiles:

| Country | 10Y bond duration |
|---|---|
| US | ≈ 8.0 |
| Germany (Bund) | ≈ 8.8 |
| Japan (JGB) | ≈ 9.5 |
| UK (Gilt) | ≈ 8.6 |
| Canada | ≈ 8.4 |
| Australia | ≈ 8.6 |
| Norway | ≈ 8.9 |
| Sweden | ≈ 8.7 |
| Switzerland | ≈ 9.4 |
| New Zealand | ≈ 8.5 |

Without normalisation, low-yield-country bonds (Japan, Switzerland)
have inflated trailing returns from the *duration* component rather
than the carry component. The strategy exposes a ``durations`` map
analogous to ``duration_targeted_momentum``; if provided, the carry
proxy is divided by per-country duration before ranking.

## In-sample period (Asness §V)

* Data: 1985–2010 monthly, G10 sovereign bond futures
* Cross-sectional carry sleeve Sharpe ≈ 0.6 over 1985–2010
* The carry signal is positively correlated with the time-series
  momentum signal at the country level (countries with high carry
  tend to also have positive recent momentum), but the
  cross-sectional view adds a relative-value dimension that
  partially decorrelates it from time-series momentum

## Implementation deviations from Asness §V

1. **Trailing-return proxy** instead of explicit yield-minus-short-
   rate carry computation. Without explicit yield curves the
   trailing return is the cleanest proxy; documented honestly in
   paper.md.
2. **Optional duration normalisation** (off by default for
   parameter parsimony). Real-feed Session 2H benchmarks should
   set this explicitly with the per-country durations.
3. **No bid-ask, FX-forward roll cost, or short-borrow model** —
   bridge applies ``commission_bps`` per leg.

## Known replications and follow-ups

* **Koijen, Moskowitz, Pedersen, Vrugt (2018)** — "Carry", JFE.
  Generalises the carry framework across asset classes and
  refines the bond-carry definition.
* **Hurst, Ooi, Pedersen (2017)** — "A Century of Evidence on
  Trend-Following Investing", AQR. Long-horizon documentation of
  bond carry alongside trend.
