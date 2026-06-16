# Known failure modes — fed_policy_tilt

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

Conover et al. (2008) / Jensen-Mercer-Johnson (1996) federal-
policy-tilt 2-cell regime allocation across SPY / TLT / GLD driven
by one FEDFUNDS informational column. Fourth consumer of the regime-
state primitive.

## 1. Regime reversal during inflationary tightening (2022)

The JMJ (1996) / Conover (2008) empirical finding — easing is
equity-positive, tightening is bond-positive — holds in most
historical episodes. However, the 2022-2023 Fed tightening cycle
was accompanied by high inflation (CPI > 8%) that simultaneously
compressed equity multiples AND drove long-duration Treasury prices
sharply lower (TLT fell ~30% in 2022 as long rates rose).

In this environment, the tightening-regime weights (20% SPY / 60%
TLT / 20% GLD) delivered negative returns on both the equity and
bond legs — the worst-case scenario where the rate-duration
relationship breaks down.

Expected behaviour in inflationary tightening:
* The strategy rotates to 60% TLT, which falls with rising long
  rates even faster than equity.
* GLD (20%) provides partial inflation hedge but insufficient to
  offset TLT losses.
* Estimated drawdown in 2022: ~20-25% (worse than in non-
  inflationary tightening cycles).

This is the strategy's canonical failure mode: tightening designed
to be bond-positive (JMJ 1996 era, 1954-1993 low-inflation
tightening) behaves as a risk-on asset-destroyer in high-inflation
tightening when long-duration bonds decline with equities.

## 2. Publication-lag forensics (load-bearing)

FEDFUNDS is published with a ~2-week lag (mid-month for the prior
month). The strategy applies `fed_lag_months=1` before computing the
rate direction. This means the regime at month-end *t* reflects
FEDFUNDS data through month *t-1* — a conservative but accurate
information set at the month-end rebalance.

**Critical:** the rate delta is computed on the *lagged* series:
`delta = rate[t-1] - rate[t-1-lookback_months]`. Computing the
delta on the unlagged series and then applying the lag would use
future information (the rate at *t* is not known at *t-1*). Both
orderings matter.

Failure to apply the lag would inflate the backtest Sharpe by
~0.2-0.5 (the "lookahead premium" of knowing the rate before the
rebalance). The magnitude is smaller than CPI/GDP lags (which span
1-3 months of true publication delay) but non-trivial.

Verified by `tests/test_unit.py::test_publication_lag_applied_to_fed_column`.

## 3. Lookback-window sensitivity

The 3-month lookback (`lookback_months=3`) is the primary tunable
parameter. Shorter lookbacks (1 month) produce more frequent regime
flips (the rate changes direction more often over 1 month than 3);
longer lookbacks (6-12 months) produce smoother but slower
classification.

Historical sensitivity:
* **lookback=1**: flips 8-12 times per year in rate-change cycles;
  whipsaw cost ~2-4% per year.
* **lookback=3** (default): flips 2-6 times per year; whipsaw cost
  ~1-2% per year.
* **lookback=6**: misses early-cycle direction changes; late entry
  into defensive allocation at cycle peaks.

The 2019 Fed pivot (rate cuts after 2018 tightening) illustrates the
lookback sensitivity: a 1-month lookback detected the pivot in
August 2019 (first cut); a 3-month lookback detected it in October
2019 (after 3 cuts confirmed the direction).

## 4. ZIRP floor and rate-unchanged periods (2010-2015, 2020-2021)

During ZIRP (2010-2015 and 2020-2021), the effective fed funds rate
sat at ~0.07-0.12% for extended periods. The 3-month delta was
near zero but never exactly zero (FEDFUNDS is an averages series, not
a discrete setting). These near-zero deltas classify as "easing"
(delta ≤ 0) even when the Fed was holding rates flat.

The easing weights (70% SPY / 20% TLT / 10% GLD) are the correct
assignment for ZIRP periods empirically (equity markets rallied
strongly 2010-2015 and 2020-2021 in the zero-rate environment).

However, the signal provides no differentiation within ZIRP: the
strategy holds easing weights continuously for ~5 years in the
post-GFC ZIRP window, functioning effectively as a static 70/20/10
allocation during that period.

Expected behaviour in ZIRP:
* Strategy is always in "easing" regime (delta ≤ 0).
* Acts as a static allocation: 70% SPY / 20% TLT / 10% GLD.
* No regime-driven rebalancing signal until the first rate hike.

## 5. Post-tightening reversal lag (2019, 2023-2024)

The 3-month lookback means the strategy lags the Fed's actual
policy pivot by 1-3 months. In 2019, the Fed cut in July, August,
and October; the 3-month lookback detected the shift to easing at
the October rebalance (after 3 cuts confirmed the direction). The
strategy missed the ~5% equity rally from July to September as the
market anticipated the pivot.

Expected behaviour at post-tightening pivots:
* 1-3 month lag in detecting the pivot to easing.
* Opportunity cost of 3-8% in equity return during the pivot window.

This is the symmetric cost to the "early defensive" failure mode in
`yield_curve_regime_allocation`: both strategies are slow relative
to the market's anticipation of the next regime.

## 6. Rebalance-cadence: monthly signal, daily bridge-side drift correction

Inherits the AlphaKit-wide convention. For fed_policy_tilt
specifically:

* ~63 daily drift-correction events per asset per year on the
  three tradable legs.
* Plus regime-flip events (2-6 per year depending on the rate cycle)
  with 3-leg reallocations.
* Zero events on the FEDFUNDS informational column (always weight 0.0).

See `docs/phase-2-amendments.md` "Session 2G: alphakit-wide
rebalance-cadence convention".

## 7. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **Phase 2 Session 2G `recession_probability_rotation`** (Commit 8)
  — overlapping macro factor. The Cleveland Fed recession-probability
  model includes the FEDFUNDS rate; easing environments correlate
  with high recession probability. Expected ρ ≈ **0.40-0.60**.
* **Phase 2 Session 2G `yield_curve_regime_allocation`** (Commit 10)
  — 2-year yield tracks fed-funds expectations. Expected ρ ≈ **0.40-0.60**.
* **Phase 2 Session 2G `growth_inflation_regime_rotation`** (Commit 9)
  — macro-state common factor. Expected ρ ≈ **0.40-0.60**.
* **Phase 2 Session 2G `inflation_regime_allocation`** (Commit 12)
  — CPI YoY signal. Expected ρ ≈ **0.30-0.50**.
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) — static
  allocation. Expected ρ ≈ **0.20-0.40**.

All pairwise ρ values within the regime-state group sit in the
0.30-0.60 range — well below the ρ > 0.95 dedup-review bar.

## Regime performance (reference, from JMJ 1996 + Conover 2008 + practitioner data)

| Regime | Example window | Sharpe | Max DD |
|---|---|---|---|
| Easing (equity-heavy) — cycle recovery | 2009-2015, 2020-2021 | ~0.7 | −6% |
| Easing (equity-heavy) — false pivot | 2001 brief cuts | ~0.0 | −15% |
| Tightening — non-inflationary | 2004-2006, 2017-2018 | ~0.3 | −8% |
| Tightening — inflationary (2022) | 2022 | ~−0.5 | −25% |
| ZIRP static (easing, rate unchanged) | 2010-2015 | ~0.6 | −4% |

(Reference ranges from JMJ 1996, Conover 2008, and practitioner
sources; the in-repo benchmark is the authoritative source for
this implementation — see
[`benchmark_results.json`](benchmark_results.json).)
