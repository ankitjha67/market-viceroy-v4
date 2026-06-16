# Paper — Recession-Probability Asset Rotation (EM 1998 / Wright 2006)

## Citations

**Initial inspiration:** Estrella, A. & Mishkin, F. S. (1998).
**Predicting U.S. Recessions: Financial Variables as Leading
Indicators.** *Review of Economics and Statistics* 80(1), 45-61.
[https://doi.org/10.1162/003465398557320](https://doi.org/10.1162/003465398557320)

**Primary methodology:** Wright, J. H. (2006). **The Yield Curve
and Predicting Recessions.** Federal Reserve Board FEDS Working
Paper 2006-07.
[https://www.federalreserve.gov/pubs/feds/2006/200607/200607pap.pdf](https://www.federalreserve.gov/pubs/feds/2006/200607/200607pap.pdf)

(Wright 2006 is a Federal Reserve Board working paper with no
DOI; cited by URL above.)

BibTeX entries are registered in `docs/papers/phase-2.bib` under
`estrellaMishkin1998predicting` (foundational) and
`wright2006yield` (primary).

## Why two papers

Estrella-Mishkin (1998) is the **foundational** reference. The
paper introduces the probit-on-financial-variables approach to
recession prediction and establishes the canonical **30%
probability threshold**: when the predicted probability of an
NBER-dated recession in the next 12 months exceeds 30%, the
model is in its "recession imminent" regime. The threshold is
robust across the 1959-1998 in-sample window and has held up in
real-time out-of-sample forecasting since.

Wright (2006) is the **production specification**. Wright extends
the Estrella-Mishkin probit with a more flexible specification
including the fed funds rate alongside the term spread, and his
specification is the one currently estimated by the Federal
Reserve Bank of Cleveland to generate the **`RECPROUSM156N`**
series on FRED. This strategy reads `RECPROUSM156N` directly
rather than re-estimating any model — so it *implements*
Wright (2006) by consuming the Cleveland Fed's published output.

Both papers are cited so the audit trail covers the foundational
model (EM 1998 → threshold + framework) and the contemporary
production specification (Wright 2006 → the specific model whose
output the strategy reads).

## Informational-column pattern (Session 2D §2D sub-section 3)

This strategy is the **first consumer** of the informational-
column pattern documented in `docs/phase-2-amendments.md` Session
2D "signal-contract clarifications" §3. The convention:

* Input `prices` DataFrame contains both **tradable** ETF columns
  (SPY, TLT, GLD) AND **informational** columns (the FRED
  recession-probability series `RECPROUSM156N`).
* Output `weights` DataFrame carries:
  - Regime-conditional allocation on the tradable columns.
  - **Weight = 0.0** on the informational columns at every bar.

The pattern is required because FRED macro variables cannot be
modelled as additional tradable assets — they are signals, not
positions. Threading them through the input DataFrame as zero-
weight columns preserves the StrategyProtocol's
`generate_signals(prices) → weights` shape contract without
requiring side-channel constructor state.

The vectorbt bridge dispatches `SizeType.TargetPercent` across
all columns; a zero-weight column is a no-op (no orders, no drift
correction) so the informational column passes through cleanly.

## Publication-lag handling (load-bearing for FRED-driven regimes)

FRED's `RECPROUSM156N` series is published with a **one-month
reporting lag**. The recession-probability estimate for month *N*
is published in month *N+1* (typically mid-month or end-of-month
depending on data-release cadence).

A naïve strategy that reads `RECPROUSM156N[month_end_N]` when
emitting weights for month-end *N* would be using **future
information** — the value at index *N* was not yet published at
month-end *N*.

The fix is to **shift the informational column by `lag_months`**
(default 1) before reading it:

    recession_prob_lagged = prices["RECPROUSM156N"].shift(lag_months)

After the shift, `recession_prob_lagged[month_end_N]` contains
the value that was last *published* before month-end *N* — i.e.
the recession probability for month *N-1*. This matches what a
real-time investor would have seen at month-end *N*.

The lag is configurable via the `lag_months` constructor
parameter for users with data sources that have different
publication cadences (e.g. a real-time Cleveland Fed feed with
weekly updates might use `lag_months=0`).

Failure to apply the lag is the **most common foot-gun in FRED-
driven regime strategies**. It is documented prominently in
`known_failures.md` item 2 with an empirical test in
`tests/test_unit.py::test_publication_lag_uses_prior_month_value`
that verifies the strategy actually applies the shift.

## Differentiation from sibling strategies

* **Phase 2 Session 2G `growth_inflation_regime_rotation`**
  (Commit 9) — uses CPI YoY and GDP growth for a 4-cell regime
  taxonomy. Same informational-column pattern; different
  regime variables and finer taxonomy. Expected ρ ≈ 0.40–0.60.
* **Phase 2 Session 2G `yield_curve_regime_allocation`**
  (Commit 10) — uses the yield-curve slope (T10Y3M), which is
  **one of the inputs** to the Cleveland Fed's recession-
  probability model. The two strategies trade highly correlated
  signals. Expected ρ ≈ **0.50–0.70** — closest within the
  regime-state group.
* **Phase 2 Session 2G `fed_policy_tilt`** (Commit 11) — uses
  fed funds rate changes. Different signal, similar pro-cyclical
  / defensive rotation mechanic. Expected ρ ≈ 0.40–0.60.
* **Phase 2 Session 2G `inflation_regime_allocation`** (Commit 12)
  — CPI YoY regimes. Different signal, different asset rotation.
  Expected ρ ≈ 0.30–0.50.
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  static allocation; this strategy is dynamic. Expected ρ ≈
  0.30–0.50.
* **Phase 2 Session 2G `risk_parity_erc_3asset`** (Commit 5)
  — different mechanic (covariance-based vs regime-based).
  Expected ρ ≈ 0.30–0.50.

## Published rules (EM 1998 / Wright 2006, 3-asset implementation)

For each month-end *t*:

1. Read the recession-probability column from `prices`, applied
   with a `lag_months` shift (default 1) to model the FRED
   publication lag.
2. Compare the lagged probability against `recession_threshold`:

   * If `recession_prob_lagged(t) < recession_threshold`:
     **risk-on**.
   * Else: **risk-off**.

3. Allocate per the configured regime weights:

   * Risk-on: `(equity_weight_risk_on, bonds_weight_risk_on,
     gold_weight_risk_on)`. Default `(0.60, 0.40, 0.00)`
     — standard 60/40 stocks/bonds.
   * Risk-off: `(equity_weight_risk_off, bonds_weight_risk_off,
     gold_weight_risk_off)`. Default `(0.00, 0.60, 0.40)`
     — long-duration Treasuries + gold.

4. Emit weights at month-end; forward-fill daily until the next
   rebalance. The informational column `RECPROUSM156N` carries
   `weight = 0.0` at every bar.

| Parameter | EM 1998 / Wright 2006 | AlphaKit default | Notes |
|---|---|---|---|
| Probability threshold | 30% (EM 1998 canonical) | 0.30 | identical |
| Publication lag | 1 month (FRED cadence) | 1 month | identical |
| Universe | n/a (paper is forecast model) | SPY / TLT / GLD | substrate-specific |
| Pro-cyclical allocation | n/a | 60% SPY / 40% TLT | substrate-specific |
| Defensive allocation | n/a | 60% TLT / 40% GLD | substrate-specific |
| Rebalance | Monthly | Monthly | identical |

The papers predict recession occurrence, not optimal asset
allocation; the weight tuples are the AlphaKit substrate-specific
implementation of "pro-cyclical → defensive" rotation triggered
by the EM 1998 threshold.

## Data Fidelity

* **Substrate:** daily closing prices from yfinance for SPY
  (1993), TLT (2002), GLD (2004) + monthly Cleveland Fed
  `RECPROUSM156N` from FRED. The continuous panel begins 2004-12
  once GLD is live; the FRED series extends back to 1959 but is
  only meaningful for our backtest from 2004 onward.
* **Publication-lag** documented above and tested in
  `tests/test_unit.py::test_publication_lag_uses_prior_month_value`.
* **Model versioning.** The Cleveland Fed periodically revises
  the underlying probit specification. Major revisions occurred
  in 2012 and 2018. The Sharpe estimates below are conditional
  on the *current* model version (as of the validation cutoff
  2025-12-31). Future revisions would require revalidation.
  Documented in `known_failures.md` item 4.
* **NaN handling.** The FRED series may have NaN values at
  recent dates (publication lag); the strategy emits zero weights
  on those bars (treated as warm-up).
* **No transaction costs in synthetic fixture.** The vectorbt
  bridge applies a configurable flat `commission_bps` per
  rebalance leg.
* **Rebalance cadence:** monthly target signal, daily bridge-side
  drift correction (AlphaKit-wide convention).

## Expected Sharpe range

`0.4 – 0.7 OOS`. The lower bound 0.4 accounts for the AlphaKit
substrate constraints (ETF-based 3-asset universe vs paper's
predictive model on raw indices) and the false-positive cost
(EM 1998 reports the 30% threshold produces ~5-10% false-positive
rate on 1959-1998 in-sample; the strategy takes a defensive
allocation cost during these false-positive months). The upper
bound 0.7 reflects the documented benefit of correctly avoiding
recession drawdowns (1973-75, 1980-82, 1990-91, 2001, 2008,
2020 March).

## Implementation deviations from EM 1998 / Wright 2006

1. **Reading `RECPROUSM156N` directly** rather than re-estimating
   the probit model. The Cleveland Fed estimates Wright (2006)'s
   specification monthly and publishes the result to FRED; the
   strategy consumes this output. Phase 3 users with the
   underlying data series (term spread, fed funds rate) could
   re-estimate the model from scratch for custom thresholds.
2. **Monthly rebalance** matches FRED's `RECPROUSM156N`
   publication cadence. Higher-frequency variants are out of
   scope.
3. **Asset allocation rule** is substrate-specific. The papers
   predict recession occurrence; the AlphaKit weight tuples
   implement the standard pro-cyclical-vs-defensive translation.
4. **3-asset substrate** instead of broader multi-asset panels.
   The 3 asset classes (equity / long bonds / gold) cover the
   recession-trade exposure cleanly without introducing
   correlation complications.
5. **No transaction-cost / financing model.** Long-only,
   no shorts, no leverage.

## Known replications and follow-ups

* **Cleveland Fed (current)** — publishes `RECPROUSM156N` monthly
  on FRED. Real-time forecasts available at
  https://www.clevelandfed.org/our-research/indicators-and-data/yield-curve-and-predicted-gdp-growth.aspx
* **Estrella, A. & Trubin, M. R. (2006)** — *The Yield Curve as a
  Leading Indicator: Some Practical Issues*. NY Fed Current Issues
  in Economics and Finance 12(5). Discusses real-time
  forecasting challenges that motivate the publication-lag
  handling in this strategy.
* **Rudebusch, G. D. & Williams, J. C. (2009)** — *Forecasting
  Recessions: The Puzzle of the Enduring Power of the Yield
  Curve*. Journal of Business & Economic Statistics 27(4),
  492-503. DOI 10.1198/jbes.2009.07213. Empirical out-of-sample
  validation of the Estrella-Mishkin / Wright framework.
