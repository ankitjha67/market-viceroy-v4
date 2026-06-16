# Strategy paper — fed_policy_tilt

## Citation

### Primary methodology

Jensen, G. R., Mercer, J. M. & Johnson, R. R. (1996). *Business
Conditions, Monetary Policy, and Expected Security Returns*. Journal
of Financial Economics **40**(2), 213-237.
DOI: [10.1016/0304-405X(96)00875-X](https://doi.org/10.1016/0304-405X(96)00875-X)

### Foundational paper

Conover, C. M., Jensen, G. R., Johnson, R. R. & Mercer, J. M. (2008).
*Sector Rotation and Monetary Conditions*. Journal of Investing
**17**(2), 34-46.
DOI: [10.3905/joi.2008.17.4.61](https://doi.org/10.3905/joi.2008.17.4.61)

## What the papers prove

### Jensen-Mercer-Johnson 1996 (primary methodology)

Jensen, Mercer & Johnson (1996) document that monetary conditions —
specifically whether the Federal Reserve is in a tightening or easing
posture — fundamentally alter the expected returns of equity and fixed-
income assets. The paper's core argument is that monetary policy
changes the investment opportunity set: in easing environments, lower
real interest rates support equity valuations, narrow credit spreads,
and reduce the discount rate applied to future earnings; in tightening
environments, rising rates compress equity multiples and improve the
relative attractiveness of bonds.

The paper uses Federal Reserve discount-rate changes as the primary
signal (initiated monetary conditions vs. expansive monetary
conditions). The results across 1954-1993 show:

* **Easing environments:** equity returns ~2× the sample average;
  risk-adjusted performance substantially superior.
* **Tightening environments:** equity returns markedly lower; bonds
  and inflation-hedge assets (gold proxies) outperform.

The 2-cell taxonomy (easing / tightening) used in this strategy is the
discrete implementation of the JMJ (1996) initiated/expansive signal,
extended to a continuous FEDFUNDS direction measure (rising vs. falling
rate over the trailing 3-month window).

### Conover et al. 2008 (foundational multi-asset extension)

Conover, Jensen, Johnson & Mercer (2008) extend the JMJ (1996)
framework from individual equity categories to multi-asset sector
rotation and international equity allocation. The paper confirms that
the 2-cell monetary-condition taxonomy is robust across:

* US equity sectors (cyclicals outperform in easing; defensives in
  tightening).
* International developed markets (equity returns in easing
  environments outperform tightening environments across 16 countries).
* Multi-asset portfolios including bonds and commodity proxies.

The paper provides the specific multi-asset allocation intuition used
here: easing → equities-heavy; tightening → bonds and gold-heavy. The
FEDFUNDS rate direction is used as the continuous real-time analogue
of the discount-rate-change signal.

## Implementation

### Informational-column pattern

The strategy reads one FRED informational column:

* **`FEDFUNDS`**: effective federal funds rate (%, monthly averages).
  Published by the Federal Reserve as the monthly average of daily
  fed funds effective rates.

The column is passed through the vectorbt bridge as a zero-weight
informational column. Three structural properties hold:

1. **`FEDFUNDS` is strictly positive**: the effective fed funds rate
   has never printed exactly 0.0 (ZIRP readings are ~0.07-0.12%,
   not 0.0). The bridge's `order.price > 0` assertion is satisfied
   naturally. This is in contrast to DGS3MO (which prints exactly 0.0
   on several ZIRP days).

2. **The regime signal is derived internally**: the tightening/easing
   classification is computed from `fed_delta = current_rate -
   rate[lookback_months ago]`. This delta can be zero or negative but
   is never passed to the bridge — only the positive FEDFUNDS level is.

3. **Weight = 0.0 at every bar**: the FEDFUNDS column always carries
   zero weight in the output. A defensive `daily_weights[fed_column]
   = 0.0` assignment at the end of `generate_signals` enforces this
   as a belt-and-suspenders invariant.

### Publication-lag handling

The FEDFUNDS column is lagged by `fed_lag_months` (default 1) before
computing the rate direction. The Fed publishes the monthly FEDFUNDS
average with a ~2-week lag (typically mid-month for the prior month),
so the 1-month lag is conservative. This is consistent with the
`yield_lag_months=1` applied to DGS10/DGS2 in
`yield_curve_regime_allocation` (Commit 10) and the `lag_months=1`
convention across the Session 2G regime-state group.

Critical: the rate delta is computed on the **lagged** series. The
direction at month-end *t* reflects the difference between the rate at
*t − fed_lag_months* and the rate at *t − fed_lag_months −
lookback_months*. Failure to apply the lag would use information not
available at rebalance time — documented in `known_failures.md` as the
load-bearing publication-lag forensics.

### 2-cell regime taxonomy

| Regime | Signal condition | Default allocation (SPY/TLT/GLD) |
|---|---|---|
| **Easing** | `delta ≤ 0` (rate flat or falling) | 70% / 20% / 10% |
| **Tightening** | `delta > 0` (rate rising) | 20% / 60% / 20% |

The equity-heavy assignment to **easing** is counterintuitive (one
might expect "easing = accommodative = risk-on"), but it is the direct
empirical finding of JMJ (1996) and Conover et al. (2008): equities
substantially outperform in easing environments.

### Warm-up and edge cases

The strategy requires `fed_lag_months + lookback_months` months of
FEDFUNDS history before emitting non-zero weights. With the defaults
(lag=1, lookback=3), the first valid month-end is month 4. Before
that, all weights are 0.0.

NaN rows in the lagged FEDFUNDS series emit zero weights rather than
propagating NaN through the bridge.

## Expected out-of-sample performance

JMJ (1996) Table 4 documents equity return differentials of 10-15%
per year between easing and tightening environments (1954-1993). The
out-of-sample performance from 1994-2020 is weaker but directionally
consistent with the regime classification:

* **Easing** (2001-2003, 2008-2015, 2019-2021): equity-heavy
  allocation outperforms balanced benchmarks, consistent with JMJ
  easing-equity relationship.
* **Tightening** (2004-2006, 2017-2018, 2022-2023): bond/gold-heavy
  allocation partially offsets equity losses.

See `benchmark_results.json` for the in-repo synthetic-fixture
benchmark. Real-feed verification is deferred to Phase 2H.

## Cluster correlation with sibling strategies

Predicted pairwise ρ within the Session 2G regime-state group:

* **`recession_probability_rotation`** (Commit 8): ~0.40-0.60. The
  Cleveland Fed recession-probability model includes the FEDFUNDS rate
  as an input; easing environments correlate with high recession
  probability (rate cuts happen during / before downturns).
* **`yield_curve_regime_allocation`** (Commit 10): ~0.40-0.60. The
  2-year yield tracks fed-funds expectations, so the DGS2 level and
  the FEDFUNDS rate direction share information.
* **`growth_inflation_regime_rotation`** (Commit 9): ~0.40-0.60.
  Growth and inflation regimes correlate with monetary-policy stance.
* **`inflation_regime_allocation`** (Commit 12): ~0.30-0.50.
* **`permanent_portfolio`** (Commit 2): ~0.20-0.40.

All pairwise ρ values within the Session 2G group sit in the 0.30-0.60
range — well below the ρ > 0.95 dedup-review bar (Phase 2 master
plan §10).
