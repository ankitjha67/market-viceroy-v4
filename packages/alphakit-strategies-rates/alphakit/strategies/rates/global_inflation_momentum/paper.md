# Paper — Global Inflation Momentum, Bond Tilt (Ilmanen/Maloney/Ross 2014)

## Citations

**Initial inspiration:** Ilmanen, A. (2011). **Expected Returns: An
Investor's Guide to Harvesting Market Rewards.** Wiley. Chapter 12
covers cross-country macro-sensitivity factors including inflation
momentum.

**Primary methodology:** Ilmanen, A., Maloney, T. & Ross, A. (2014).
**Exploring macroeconomic sensitivities: How investments respond to
different economic environments.** *Journal of Portfolio
Management*, 40(3), 87–99.
[https://doi.org/10.3905/jpm.2014.40.3.087](https://doi.org/10.3905/jpm.2014.40.3.087)

BibTeX entries: `ilmanen2011expected` (foundational, book) and
`ilmanenMaloneyRoss2014macro` (primary, JPM article) in
`docs/papers/phase-2.bib`.

## Why two papers

Ilmanen (2011) is the textbook *foundational* synthesis of macro
factor investing. The chapter on inflation regimes establishes
the *risk-factor* framework: bonds underperform when inflation
rises and outperform when it falls, and the inflation-rate change
is itself persistent (mean-reverts only over multi-year horizons).

Ilmanen/Maloney/Ross (2014) is the explicit *expected-return*
paper that operationalises this framework into a tradeable signal:
country-level inflation momentum predicts country-level bond
returns negatively, and the cross-sectional rank produces a
dollar-neutral relative-value trade.

The synthesis is the explicit cross-country inflation-momentum-
driven bond tilt implemented here.

## Differentiation from sibling strategies

* **`breakeven_inflation_rotation`** — single-country (US-only)
  rotation between TIPS and nominal Treasury based on breakeven
  *level*. Different signal type (level vs momentum), different
  country scope (US-only vs G10).
* **`real_yield_momentum`** — TIPS-derived bond momentum on US
  real yields. Single-country, momentum mechanic on bond price
  (not inflation).
* **`g10_bond_carry`** — cross-country bond carry on yield levels.
  Same country scope but different signal (carry, not inflation
  momentum).

The four inflation/cross-country/momentum strategies in the
family are deliberately constructed to trade orthogonal slices
of the same macro space.

## Algorithm

The strategy expects a multi-column ``prices`` DataFrame with
**paired columns**: each country provides one ``CPI_<country>``
column (CPI level proxy) and one ``BOND_<country>`` column. Country
labels must match exactly: ``CPI_US`` pairs with ``BOND_US``.

For each month-end:

1. **Inflation momentum** per country = trailing 12-month log
   change in the CPI level proxy.
2. **Cross-sectional rank** of inflation momentum across
   countries.
3. **Bond weights:** dollar-neutral on the BOND_ columns. *Long*
   the bond of the country with the *lowest* inflation momentum
   (falling inflation → bonds rally); *short* the bond of the
   country with the *highest* inflation momentum (rising
   inflation → bonds fall). Sign is negative demeaned-rank.
4. CPI_ columns receive zero weight (informational only).
5. Forward-fill monthly weights to daily.

| Parameter | Default | Notes |
|---|---|---|
| `cpi_lookback_months` | `12` | Ilmanen/Maloney/Ross horizon |

## Why a 2K-column input convention

The strategy needs both CPI data (for the signal) and bond data
(for the trade). The cleanest way to express this in a single
``prices: pd.DataFrame`` interface is the column-naming
convention: ``CPI_X`` and ``BOND_X`` for each country X. The
strategy validates the pairing at runtime and raises ``ValueError``
on:

* Columns not following the naming convention
* CPI columns without matching BOND counterparts (or vice versa)
* Fewer than 2 countries (cross-sectional rank requires N >= 2)

## In-sample period (Ilmanen/Maloney/Ross 2014)

* Data: 1972–2013 monthly, multi-country CPI and bond returns
* Bond Sharpe in falling-inflation regime: ~+1.0
* Bond Sharpe in rising-inflation regime: ~−0.5 to −1.0
* Cross-sectional inflation-momentum sleeve Sharpe: ~0.5-0.7
  over the full sample, less in low-inflation-volatility
  sub-periods

## Implementation deviations from IMR (2014)

1. **CPI level proxy via log-change instead of YoY %-change of
   the YoY index.** Both are close approximations for moderate
   inflation; YoY of YoY is preferred for high-inflation regimes
   but the log-change is the cleaner default.
2. **No FX hedging on the bond returns.** As with `g10_bond_carry`,
   the strategy operates on whatever bond price series are passed
   in; FX exposure is implicit unless the inputs are FX-hedged
   USD-equivalent series.
3. **No survey-expectations adjustment.** IMR (2014) experiments
   with subtracting consensus inflation forecasts to isolate
   *surprise* inflation; this implementation uses the realised
   inflation momentum as the simpler, reproducible signal.

None of these change the *sign* of the trade relative to the
paper's economic content.

## Known replications and follow-ups

* **Asness, Moskowitz, Pedersen (2013)** §V — cross-asset
  momentum framework that includes country-level bond momentum;
  IMR's inflation-momentum signal is a refinement.
* **Cieslak, Povala (2015)** — "Expected Returns in Treasury
  Bonds", RFS. Refines bond-return forecasting with inflation
  expectations as an additional state variable.
