# Paper — Yield-Curve Slope Regime Allocation (EH 1991 / APW 2006)

## Citations

**Initial inspiration:** Estrella, A. & Hardouvelis, G. A. (1991).
**The Term Structure as a Predictor of Real Economic Activity.**
*Journal of Finance* 46(2), 555-576.
[https://doi.org/10.1111/j.1540-6261.1991.tb03775.x](https://doi.org/10.1111/j.1540-6261.1991.tb03775.x)

**Primary methodology:** Ang, A., Piazzesi, M. & Wei, M. (2006).
**What Does the Yield Curve Tell Us about GDP Growth?** *Journal
of Econometrics* 131(1-2), 359-403.
[https://doi.org/10.1016/j.jfineco.2005.05.005](https://doi.org/10.1016/j.jfineco.2005.05.005)

BibTeX entries are registered in `docs/papers/phase-2.bib` under
`estrellaHardouvelis1991term` (foundational) and
`angPiazzesiWei2006yield` (primary).

## Why two papers

Estrella-Hardouvelis (1991) is the **foundational** result. The
paper documents that the slope of the Treasury yield curve (the
long-minus-short spread) forecasts real economic activity — GDP
growth, consumption, investment — 1-4 quarters ahead, and that a
flat or inverted curve forecasts recessions. It is the seminal
"yield curve as leading indicator" reference and established the
empirical foundation that the modern recession-prediction
literature (including the Cleveland Fed model consumed by Commit
8's `recession_probability_rotation`) builds on.

Ang-Piazzesi-Wei (2006) is the **modern methodology**. APW build a
no-arbitrage dynamic term-structure model and show that the
*slope* of the term structure is the single most informative
yield-curve summary statistic for forecasting GDP growth —
dominating the level and curvature factors. The 3-cell regime
taxonomy (steep / flat / inverted) is the discrete implementation
of the APW continuous slope signal.

Both papers are cited so the audit trail covers the foundational
finding (EH 1991 → slope predicts activity / recessions) and the
modern term-structure framework (APW 2006 → slope is the dominant
GDP-forecasting factor).

## Informational-column pattern + internal slope computation

Inherits the informational-column pattern (Session 2D §2D
sub-section 3). This strategy reads **two** raw yield-level
informational columns and computes the slope internally:

* `DGS10`: 10-year Treasury constant-maturity yield (%).
* `DGS2`: 2-year Treasury constant-maturity yield (%).

The yield-curve slope `= DGS10 - DGS2` is computed *inside*
`generate_signals`. The slope **goes negative on inversion** —
which is exactly the recession-warning regime the strategy cares
about — so the slope itself can never be an informational column
passed through the bridge (the vectorbt bridge rejects
non-positive `close` prices; see `docs/phase-2-amendments.md`
"Session 2G: informational columns must be positive-valued"). The
two raw yield *levels* are strictly positive, so they pass through
cleanly; the (possibly negative) slope is a transient local
variable that never reaches the bridge.

Both informational columns carry **weight = 0.0** in the output;
only the three tradable ETF columns (SPY, TLT, GLD) carry the
regime-conditional allocation.

## Why DGS2 (2-year) instead of DGS3MO (3-month)

Estrella-Hardouvelis (1991) originally uses the 10-year minus
3-month spread, and the Cleveland Fed recession-probability model
(consumed by Commit 8's `recession_probability_rotation`) uses the
same 10y-3m spread. The natural short leg would therefore be
`DGS3MO`.

However, `DGS3MO` prints exactly `0.0` on several zero-interest-
rate-policy days (2011, 2020-2021). Because the informational
columns pass through the vectorbt bridge as `close` prices (which
must be strictly positive), a `0.0` print would trip the bridge's
`order.price > 0` assertion even though the column is
informational and carries weight 0.

`DGS2` (2-year) is used instead: the 2-year yield always carries a
term premium and stays strictly positive even at the ZIRP lower
bound. The 2s10s slope is ~0.9-correlated with the 10y-3m measure
and carries the same economic content (curve slope), so:

* The Estrella-Hardouvelis (1991) and APW (2006) slope-predicts-
  activity thesis applies unchanged (both papers discuss the slope
  generically; 2s10s is a standard slope measure).
* The cross-strategy cluster prediction with
  `recession_probability_rotation` (ρ ≈ 0.50-0.70) holds because
  2s10s and 10y-3m are ~0.9 correlated.

This choice is documented in `docs/phase-2-amendments.md` and
`known_failures.md`.

## Differentiation from sibling strategies

* **Phase 2 Session 2G `recession_probability_rotation`**
  (Commit 8) — closest cluster sibling. The Cleveland Fed
  recession-probability model uses the yield-curve slope (10y-3m)
  as its primary input, so this strategy's slope signal and
  Commit 8's recession-probability signal are driven by
  overlapping information. Expected ρ ≈ **0.50-0.70** — the
  highest within the regime-state group. Documented as a
  deliberate family pair below the Phase 2 master plan §10
  dedup-review bar (ρ > 0.95).
* **Phase 2 Session 2G `growth_inflation_regime_rotation`**
  (Commit 9) — CPI + GDP signal, 4-cell. Expected ρ ≈ 0.40-0.60.
* **Phase 2 Session 2G `fed_policy_tilt`** (Commit 11) — fed
  funds rate signal. The 2-year yield is closely tied to fed-funds
  expectations, so there is some signal overlap. Expected ρ ≈
  0.40-0.60.
* **Phase 2 Session 2G `inflation_regime_allocation`** (Commit 12)
  — CPI YoY signal. Expected ρ ≈ 0.30-0.50.
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  static allocation. Expected ρ ≈ 0.30-0.50.

## Published rules (EH 1991 / APW 2006, 3-asset implementation)

For each month-end *t*:

1. Read the two yield columns, apply `yield_lag_months` shift.
2. Compute the slope `= DGS10 - DGS2` on the lagged series.
3. Classify the regime:
   * `slope >= steep_threshold` (default 1.0%) → steep.
   * `flat_threshold <= slope < steep_threshold` → flat.
   * `slope < flat_threshold` (default 0.0) → inverted.
4. Map the regime to its configured allocation:

   | Regime | Default (SPY/TLT/GLD) | Rationale |
   |---|---|---|
   | steep | (0.70, 0.30, 0.00) | strong-growth forecast → equity-heavy |
   | flat | (0.40, 0.40, 0.20) | neutral → balanced |
   | inverted | (0.00, 0.60, 0.40) | recession warning → defensive |

5. Emit weights at month-end; forward-fill daily. Both yield
   columns carry `weight = 0.0`.

| Parameter | EH 1991 / APW 2006 | AlphaKit default | Notes |
|---|---|---|---|
| Slope measure | 10y-3m (EH) / slope factor (APW) | 10y-2y | substrate: DGS2 for ZIRP positivity |
| Regime taxonomy | steep / flat / inverted | identical | identical |
| Steep threshold | n/a (continuous) | 1.0% | substrate-specific |
| Inversion threshold | 0% (negative slope) | 0.0% | identical |
| Universe | n/a (papers are forecast models) | SPY/TLT/GLD | substrate-specific |
| Rebalance | n/a | monthly | substrate-specific |

The papers forecast economic activity from the slope; the weight
tuples are the AlphaKit substrate translation of "steep → growth →
equity; inverted → recession → defensive".

## Data Fidelity

* **Substrate:** daily yfinance prices for SPY (1993), TLT (2002),
  GLD (2004) + daily FRED DGS10 + DGS2. Continuous panel from
  2004-12 once GLD is live.
* **DGS2 over DGS3MO** for bridge-positivity (see "Why DGS2").
* **Yields published daily** with negligible lag; the
  `yield_lag_months=1` shift is applied for parity with the
  other regime-state strategies (conservative month-end
  information set).
* **No transaction costs in synthetic fixture.** The bridge
  applies a configurable flat `commission_bps`.
* **Rebalance cadence:** monthly target signal, daily bridge-side
  drift correction (AlphaKit-wide convention).

## Expected Sharpe range

`0.4 – 0.7 OOS`. The yield-curve slope is a well-documented
leading indicator (EH 1991, APW 2006), but as a *tradable* signal
it inherits the same false-positive and lead-time issues as the
recession-probability approach. The lower bound 0.4 reflects
false-positive inversions (the curve inverted in 1998 and 2019
without an immediate recession) and the early-warning lead time
(the curve often inverts 12-18 months before the recession, so a
defensive rotation can be early). The upper bound 0.7 reflects
clean recession-avoidance in 2001, 2008, and 2020.

## Implementation deviations from EH 1991 / APW 2006

1. **2s10s slope** (DGS10 - DGS2) instead of EH's 10y-3m spread.
   See "Why DGS2". The two measures are ~0.9 correlated; the
   substrate choice is for bridge-positivity robustness.
2. **3-cell discrete regime** instead of APW's continuous slope
   regression. The discrete taxonomy is the tradable implementation
   of the continuous forecast signal; thresholds are configurable.
3. **Threshold-based classification** with fixed steep (1.0%) and
   inversion (0.0%) boundaries instead of a fitted probit. The
   thresholds are reasonable defaults; users can tune via the
   constructor.
4. **3-asset substrate** instead of the broader macro panels in
   the source papers.
5. **No transaction-cost / financing model.** Long-only.

## Known replications and follow-ups

* **Estrella, A. & Mishkin, F. S. (1998)** — *Predicting U.S.
  Recessions: Financial Variables as Leading Indicators*. RES
  80(1). The recession-probability formalisation of the EH 1991
  yield-curve signal; cited by Commit 8's
  `recession_probability_rotation`. The two strategies are the
  continuous-slope (this strategy) and probit-probability (Commit
  8) implementations of the same underlying yield-curve signal.
* **Bauer, M. D. & Mertens, T. M. (2018)** — *Economic Forecasts
  with the Yield Curve*. FRBSF Economic Letter 2018-07. Modern
  real-time validation of the slope-predicts-recession result;
  finds the 10y-3m and 10y-2y spreads have comparable forecasting
  power.
* **Cleveland Fed (current)** — publishes the yield-curve-based
  recession probability monthly (RECPROUSM156N), the production
  output that Commit 8 consumes.
