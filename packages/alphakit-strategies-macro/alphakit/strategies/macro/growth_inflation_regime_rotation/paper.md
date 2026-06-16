# Paper — Growth × Inflation 4-Cell Macro Regime Rotation (IMR 2014)

## Citation

**Primary methodology (sole anchor):** Ilmanen, A., Maloney, T. &
Ross, A. (2014). **Exploring Macroeconomic Sensitivities: How
Investments Respond to Different Economic Environments.** *Journal
of Portfolio Management* 40(3), 87-99.
[https://doi.org/10.3905/jpm.2014.40.3.087](https://doi.org/10.3905/jpm.2014.40.3.087)

BibTeX entry is registered in `docs/papers/phase-2.bib` under
`ilmanenMaloneyRoss2014macro` (already registered by the rates-
family `global_inflation_momentum` in Session 2D and reused here).

## Why a single-paper anchor

IMR (2014) is cited as a **sole anchor**, matching the Session 2F
precedent of `calendar_spread_atm` citing Goyal/Saretto (2009) as
the single anchor. The single-paper pattern is appropriate when one
paper specifies *both* the construction and the empirical evidence:

* **The construction:** IMR's growth × inflation 4-cell taxonomy is
  the canonical academic formalisation of the four-quadrant macro
  framework. The paper decomposes the macroeconomic environment
  into four cells defined by the cross of growth (rising vs falling
  relative to trend) and inflation (rising vs falling relative to
  trend).
* **The empirical sensitivities:** IMR documents the asset-class
  returns in each cell across a multi-decade sample, producing the
  asset-class sensitivities that drive the regime-conditional
  allocation. No separate foundational paper is needed — IMR
  specifies both the *what* (the taxonomy) and the *how much* (the
  empirical sensitivities).

The four cells and their documented asset-class sensitivities:

* **Rising growth + rising inflation ("overheating"):** equities
  and commodities outperform; bonds underperform (rising rates
  hurt duration).
* **Rising growth + falling inflation ("goldilocks"):** equities
  and bonds both outperform — the best regime for a balanced
  stock/bond book.
* **Falling growth + rising inflation ("stagflation"):** real
  assets (gold, commodities) outperform; equities and bonds both
  struggle.
* **Falling growth + falling inflation ("deflation / recession"):**
  long-duration bonds outperform as yields fall; equities and
  commodities underperform.

## Informational-column pattern (Session 2D §2D sub-section 3)

Inherits the pattern established by Commit 8
(`recession_probability_rotation`). This strategy uses **two**
informational columns:

* `CPIAUCSL`: CPI All Urban Consumers (index level). The strategy
  computes year-over-year inflation internally
  (`pct_change(12 months) × 100`) — the input is the raw FRED
  index, not a pre-computed rate.
* `GDPC1`: Real Gross Domestic Product (chained-dollar *level*,
  quarterly, always positive). The strategy computes year-over-
  year growth internally (`pct_change(12 months) × 100`) — same
  treatment as CPI.

Both informational columns carry **weight = 0.0** in the output;
only the four tradable ETF columns (SPY, TLT, GLD, DBC) carry the
regime-conditional allocation. The vectorbt bridge dispatches
`SizeType.TargetPercent` across all columns; zero-weight columns
are no-ops.

### Why GDPC1 (level) instead of A191RL1Q225SBEA (growth rate)

The Session 2G plan originally specified the GDP *growth rate*
series `A191RL1Q225SBEA`, which goes **negative** in recessions.
The vectorbt bridge treats every input column — including
informational columns — as a `close` price and **rejects
non-positive prices** (`order.price must be finite and greater
than 0`), even for zero-weight columns. A negative-valued
informational column therefore breaks the bridge. The fix is to
consume the GDP *level* series `GDPC1` (always positive) and
compute YoY growth internally — parallel to the CPI index → YoY
treatment. The architectural constraint — *informational columns
passed through the vectorbt bridge must be positive-valued* — is
documented in `known_failures.md` and applies to all FRED-driven
regime strategies (FEDFUNDS and CPIAUCSL are naturally positive;
only the GDP growth-rate series needed the level-vs-rate switch).

## Publication-lag handling (two separate lags)

Inherits the load-bearing publication-lag discipline established by
Commit 8, extended to two separately-lagged columns:

* **CPI lag** (`cpi_lag_months`, default 1): CPI is released
  ~mid-month for the *prior* month, so a 1-month lag models the
  real-time availability.
* **GDP lag** (`gdp_lag_months`, default 1): GDP is released
  quarterly with an ~1-month lag after quarter-end (advance
  estimate), with subsequent revisions 2-3 months out. The default
  1-month lag models advance-estimate availability; users wanting
  to model the final-revision availability should set
  `gdp_lag_months=3`. The quarterly cadence means the GDP
  *level* value forward-fills within each quarter when resampled
  to month-end; the YoY growth is then computed on the lagged
  forward-filled level.

**Critical:** the CPI YoY is computed *after* the lag is applied,
so the 12-month look-back operates on the publication-lagged
series. This avoids the foot-gun of computing YoY on the
unlagged series and then lagging the result (which would mix
real-time and revised vintages). Verified by
`tests/test_unit.py::test_publication_lag_applied_to_both_columns`.

## Differentiation from sibling strategies

* **Phase 2 Session 2G `recession_probability_rotation`**
  (Commit 8) — single informational column, 2-cell regime. This
  strategy uses two informational columns (CPI + GDP) and a finer
  4-cell taxonomy. Expected ρ ≈ **0.40–0.60** (overlapping
  macro-state common factor — the falling-growth cells of this
  strategy correlate with the high-recession-probability regime
  of Commit 8).
* **Phase 2 Session 2G `yield_curve_regime_allocation`**
  (Commit 10) — yield-curve slope signal, 3-cell. Expected ρ ≈
  0.40–0.60.
* **Phase 2 Session 2G `fed_policy_tilt`** (Commit 11) — fed
  funds rate signal, 2-cell. Expected ρ ≈ 0.40–0.60.
* **Phase 2 Session 2G `inflation_regime_allocation`** (Commit 12)
  — CPI-only 3-cell. This strategy's inflation dimension overlaps
  with Commit 12's signal. Expected ρ ≈ 0.40–0.60.
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  static allocation. Expected ρ ≈ 0.30–0.50.

## Published rules (IMR 2014, 4-asset implementation)

For each month-end *t*:

1. Read CPI index column, apply `cpi_lag_months` shift, compute
   YoY inflation = `pct_change(12) × 100` on the lagged series.
2. Read GDP level column, apply `gdp_lag_months` shift, compute
   YoY growth = `pct_change(12) × 100` on the lagged series.
3. Classify the growth state (rising/falling vs `growth_threshold`)
   and the inflation state (rising/falling vs
   `inflation_threshold`).
4. Map the (growth, inflation) cell to its configured allocation:

   | Growth | Inflation | Default (SPY/TLT/GLD/DBC) | Regime |
   |---|---|---|---|
   | rising | rising | (0.40, 0.00, 0.20, 0.40) | overheating |
   | rising | falling | (0.60, 0.40, 0.00, 0.00) | goldilocks |
   | falling | rising | (0.00, 0.20, 0.40, 0.40) | stagflation |
   | falling | falling | (0.15, 0.70, 0.15, 0.00) | deflation |

5. Emit weights at month-end; forward-fill daily. Both
   informational columns carry `weight = 0.0`.

| Parameter | IMR 2014 | AlphaKit default | Notes |
|---|---|---|---|
| Regime taxonomy | 4-cell growth × inflation | identical | identical |
| Growth measure | GDP growth vs trend | GDP rate vs 2.0% threshold | substrate-specific threshold |
| Inflation measure | CPI vs trend | CPI YoY vs 2.5% threshold | substrate-specific threshold |
| Asset sensitivities | per-cell empirical | regime_weights tuples | IMR documented sensitivities |
| Rebalance | n/a (paper is analysis) | monthly | substrate-specific |

The asset-class sensitivities in IMR 2014 are documented as
*directional* (which asset classes outperform in each cell); the
specific weight tuples are the AlphaKit substrate translation of
those directional sensitivities into long-only allocations.

## Data Fidelity

* **Substrate:** daily yfinance prices for SPY (1993), TLT (2002),
  GLD (2004), DBC (2006) + monthly FRED CPIAUCSL + quarterly FRED
  GDPC1. Continuous panel from 2006-02 once DBC is live.
* **CPI YoY computed post-lag** (see "Publication-lag handling").
* **GDP quarterly cadence** forward-fills within quarters when
  resampled to month-end. The growth state therefore updates at
  most quarterly even though the strategy rebalances monthly.
* **No transaction costs in synthetic fixture.** The bridge
  applies a configurable flat `commission_bps`.
* **Rebalance cadence:** monthly target signal, daily bridge-side
  drift correction (AlphaKit-wide convention).

## Expected Sharpe range

`0.4 – 0.7 OOS`. IMR 2014 does not report a tradable strategy
Sharpe (the paper is a macro-sensitivity analysis, not a strategy
backtest), so the range is anchored to the documented asset-class
sensitivities: correctly rotating into the outperforming asset
classes in each regime cell produces a Sharpe in the same band as
the other Session 2G regime-state strategies (0.4-0.7). The lower
bound reflects regime-boundary whipsaw cost; the upper bound
reflects clean regime capture in persistent macro environments
(2010-2014 goldilocks; 2021-2022 overheating → stagflation
transition).

## Implementation deviations from IMR 2014

1. **Threshold-based classification** instead of IMR's continuous
   trend-relative measure. IMR classifies growth/inflation as
   rising/falling relative to a trend; the AlphaKit implementation
   uses fixed thresholds (2.0% GDP, 2.5% CPI) for determinism and
   reproducibility. The thresholds are configurable.
2. **GDP YoY computed from the level series** (GDPC1) rather than
   reading a pre-computed growth rate or computing a
   growth surprise vs forecast. IMR uses growth relative to
   trend/expectation; the AlphaKit implementation uses the
   trailing-12-month real GDP growth vs a fixed threshold.
3. **4-asset substrate.** IMR analyses a broader multi-asset
   panel; the AlphaKit implementation uses 4 ETFs (equity / long
   bonds / gold / commodities) covering the four asset classes
   that span the regime sensitivities.
4. **No transaction-cost / financing model.** Long-only.

## Known replications and follow-ups

* **Ilmanen, A. (2011)** — *Expected Returns: An Investor's Guide
  to Harvesting Market Rewards*, Wiley (ISBN 978-1119990727). Ch
  8-12 develop the macro-sensitivity framework that IMR 2014
  formalises. Cited as the foundational reference for the rates-
  family `global_inflation_momentum` in Session 2D.
* **Bridgewater (All-Weather)** — the four-quadrant macro
  framework is the conceptual basis for Bridgewater's All-Weather
  fund. The construction has never been published in detail; IMR
  2014 is the peer-reviewed academic equivalent.
* **Greer, R. J. (1997)** — *What is an Asset Class, Anyway?*,
  Journal of Portfolio Management 23(2). Establishes the
  asset-class taxonomy (capital assets / consumable-transformable
  / store-of-value) that maps to the equity / bond / commodity /
  gold legs used here.
