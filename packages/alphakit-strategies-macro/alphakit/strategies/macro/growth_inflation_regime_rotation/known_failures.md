# Known failure modes — growth_inflation_regime_rotation

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

IMR (2014) growth × inflation 4-cell macro regime rotation across
SPY / TLT / GLD / DBC driven by two FRED informational columns
(CPI index → YoY; GDP level → YoY). Second consumer of the
regime-state primitive; inherits the informational-column +
publication-lag pattern from Commit 8.

## 1. Regime-boundary whipsaw

The 4-cell regime classification uses hard thresholds (GDP > 2.0%
for rising growth; CPI YoY > 2.5% for rising inflation). When
either signal oscillates near its threshold, the regime flips
between adjacent cells, producing whipsaw turnover.

Worst case: both signals oscillate near their thresholds
simultaneously, cycling through all four cells within a few
months. Each cell has a materially different allocation (e.g.
goldilocks is 60% SPY / 40% TLT while stagflation is 0% SPY /
20% TLT / 40% GLD / 40% DBC), so a boundary oscillation produces
large turnover.

Expected behaviour near regime boundaries:

* 200-400% notional turnover per regime flip (full reallocation
  across 4 legs).
* Cumulative whipsaw cost of 2-6% per year when both signals
  hover near thresholds (e.g. 2012-2013 when GDP growth oscillated
  around 2% and inflation around 2%).

Mitigation: widen the threshold deadbands or add a confirmation
lag (require N consecutive months in a new cell before
rotating). Out of scope for this commit; the constructor exposes
`growth_threshold` and `inflation_threshold` for tuning.

## 2. GDP quarterly-cadence lag (compounds the publication lag)

GDP (GDPC1, the real GDP *level*) is released **quarterly**, not
monthly. When resampled to month-end, the GDP level forward-fills
within each quarter (and the internal YoY computation operates on
the forward-filled level). Combined with the `gdp_lag_months`
publication lag, the growth-state classification can be **stale by
up to 4 months** at the start of a new quarter:

* The Q1 GDP advance estimate is released ~late April (1 month
  after quarter-end).
* With `gdp_lag_months=1`, the strategy reads the Q1 value at
  May month-end.
* So the growth state at May month-end reflects Q1 economic
  conditions — already 2 months stale, and it stays fixed through
  the May/June/July month-ends until the Q2 estimate arrives.

This is a structural feature of using quarterly GDP. In sharp
growth transitions (2008 Q4, 2020 Q2), the growth-state
classification lags the actual economic reality by a full
quarter. Documented as a cost of the quarterly GDP cadence.

Mitigation: Phase 3 users could substitute a monthly growth proxy
(e.g. the Chicago Fed National Activity Index, CFNAI) for GDP via
the `gdp_column` parameter — monthly cadence would reduce the
staleness to the publication lag only. Note: any substitute must
be a **positive-valued** series (see item 3) — CFNAI goes
negative, so it would need to be consumed as a level or shifted
into positive territory.

## 2b. Informational columns must be positive-valued (bridge constraint)

The vectorbt bridge treats every input column — including the
informational FRED columns — as a `close` price and **rejects
non-positive prices** (`order.price must be finite and greater
than 0`), even though the informational columns carry weight 0.0.

This is why the strategy consumes the GDP *level* series `GDPC1`
(always positive) and computes YoY internally, rather than the
GDP *growth-rate* series `A191RL1Q225SBEA` (which goes negative
in recessions and would break the bridge). The discovery and fix
happened during Commit 9 benchmark generation: an initial GDP
growth-rate panel with a -3% (2020) value triggered the bridge's
positive-price assertion.

The constraint applies to all FRED-driven regime strategies in
the Session 2G regime-state group:

* `recession_probability_rotation` (RECPROUSM156N): probability in
  [0, 1] — naturally positive. ✓
* `growth_inflation_regime_rotation` (CPIAUCSL + GDPC1): both are
  index/level series — naturally positive. ✓ (after the
  level-vs-rate switch)
* `yield_curve_regime_allocation` (DGS10 + DGS2): the yield-curve
  slope **goes negative** (inversion!) so the spread itself cannot
  be an informational column. Commit 10 reads the two raw yield-
  *level* columns (DGS10, DGS2 — both strictly positive) and
  computes the slope internally. `DGS2` is used over `DGS3MO`
  because `DGS3MO` prints exactly `0.0` on ZIRP days (2011,
  2020-2021); the 2-year always carries a term premium. ✓
* `fed_policy_tilt` (FEDFUNDS): rate level — naturally positive. ✓
* `inflation_regime_allocation` (CPIAUCSL): index — naturally
  positive. ✓

This is a load-bearing constraint for the regime-state group and
is documented in `docs/phase-2-amendments.md`.

## 3. Publication-lag forensics (inherited from Commit 8)

Inherits the load-bearing publication-lag discipline from
`recession_probability_rotation/known_failures.md` item 2,
extended to two separately-lagged columns:

* CPI lag (`cpi_lag_months=1`): models the ~mid-month CPI release.
* GDP lag (`gdp_lag_months=1`): models the advance-estimate
  release.

**Critical:** the CPI YoY is computed *after* the lag is applied,
so the 12-month look-back operates on the publication-lagged
series. Computing YoY first and then lagging the result would mix
real-time and revised vintages. Verified by
`tests/test_unit.py::test_publication_lag_applied_to_both_columns`.

Failure to apply either lag would inflate the backtest Sharpe by
the value of the foresight (~0.3-0.8 Sharpe depending on the
regime-capture quality), which is not available in production.

## 4. Threshold sensitivity

The 2.0% GDP and 2.5% CPI thresholds are reasonable defaults but
materially affect the regime classification. Lowering the
inflation threshold to 2.0% (closer to the Fed target) would
classify more periods as "rising inflation", tilting the
allocation toward gold/commodities more often. Raising the GDP
threshold to 3.0% would classify more periods as "falling
growth", tilting toward bonds.

The Sharpe in `benchmark_results.json` is conditional on the
default thresholds. Users tuning the thresholds should expect
materially different regime distributions and hence different
Sharpe / drawdown profiles.

## 5. Mis-classification at regime transitions

The 4-cell taxonomy assumes the four regimes are well-separated.
In practice, transitions are gradual: the economy spends months
in ambiguous states where growth and inflation are both near
their thresholds. During these transitions the strategy may
classify the regime "wrong" relative to the realised asset-class
performance, producing the under-performance the IMR sensitivities
warn against.

2021-2022 illustrates this acutely: the transition from
"overheating" (2021, rising growth + rising inflation) to
"stagflation" (2022, falling growth + rising inflation) took
several months, during which the strategy held overheating
weights (40% SPY / 40% DBC / 20% GLD) into the 2022 equity
drawdown before flipping to stagflation weights.

Expected behaviour at regime transitions:

* 1-3 month lag in recognising the new regime.
* Drawdown of 5-15% during the misclassified transition window.

## 6. Rebalance-cadence: monthly signal, daily bridge-side drift correction

Inherits the AlphaKit-wide convention. For
growth_inflation_regime_rotation specifically:

* ~63 daily drift-correction events per asset per year on the
  four tradable legs.
* Plus regime-flip events (0-6 per year depending on threshold
  proximity) with large 4-leg reallocations.
* Zero events on both informational columns (CPIAUCSL, GDPC1
  always weight 0.0).

See `docs/phase-2-amendments.md` "Session 2G: alphakit-wide
rebalance-cadence convention".

## 7. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **Phase 2 Session 2G `recession_probability_rotation`**
  (Commit 8) — overlapping macro-state common factor. The
  falling-growth cells of this strategy correlate with the
  high-recession-probability regime of Commit 8. Expected ρ ≈
  **0.40–0.60**.
* **Phase 2 Session 2G `inflation_regime_allocation`** (Commit 12)
  — this strategy's inflation dimension overlaps with Commit 12's
  CPI-only signal. Expected ρ ≈ 0.40–0.60.
* **Phase 2 Session 2G `yield_curve_regime_allocation`**
  (Commit 10) — yield-curve slope signal. Expected ρ ≈ 0.40–0.60.
* **Phase 2 Session 2G `fed_policy_tilt`** (Commit 11) — fed
  funds rate signal. Expected ρ ≈ 0.40–0.60.
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  static allocation. Expected ρ ≈ 0.30–0.50.

All pairwise ρ values within the Session 2G regime-state group
sit in the 0.30-0.60 range — substantial macro-state common
factor but well below the Phase 2 master plan §10 deduplication-
review bar (ρ > 0.95).

## Regime performance (reference, from IMR 2014 sensitivities + practitioner data)

| Regime cell | Example window | Sharpe | Max DD |
|---|---|---|---|
| Goldilocks (rising growth, falling inflation) | 2013-2015 | ~0.8 | −6% |
| Overheating (rising growth, rising inflation) | 2021 | ~0.6 | −8% |
| Stagflation (falling growth, rising inflation) | 2022 | ~0.3 | −12% (transition lag) |
| Deflation (falling growth, falling inflation) | 2008-Q4, 2020-Q1 | ~0.5 | −15% (TLT rally offsets equity) |
| Mixed / boundary whipsaw | 2012, 2015-16 | ~0.0 to 0.3 | −10% (turnover cost) |

(Reference ranges from IMR 2014 documented sensitivities +
practitioner sources; the in-repo benchmark is the authoritative
source for this implementation — see
[`benchmark_results.json`](benchmark_results.json).)
