# Paper — Duration-Targeted Momentum (Durham 2015)

## Citation

**Primary methodology:** Durham, J. B. (2015). **Momentum and the
term structure of interest rates.** *Federal Reserve Board, Finance
and Economics Discussion Series* 2015-103.
[https://www.federalreserve.gov/econresdata/feds/2015/files/2015103pap.pdf](https://www.federalreserve.gov/econresdata/feds/2015/files/2015103pap.pdf)

DOI: [10.17016/FEDS.2015.103](https://doi.org/10.17016/FEDS.2015.103)

BibTeX entry: `durham2015momentum` in `docs/papers/phase-2.bib`.

## Why a single primary citation

Durham (2015) is the foundational and the methodology paper for this
construction. The duration-adjusted ranking he documents is what is
implemented; no separate foundational paper is required, and the
"Why two papers" section is intentionally absent. The general
convention used in this family is that single-paper strategies omit
the section to keep paper.md focused on the implementation source.

## Differentiation from sibling momentum strategies

* **`bond_tsmom_12_1`** — *single-asset* sign-of-12/1-return on a
  single bond. Uses raw price returns without duration adjustment.
  Trades outright duration when the trailing return is positive.
* **`duration_targeted_momentum`** (this strategy) — *cross-sectional*
  rank on duration-adjusted 12/1 returns. Long top quantile, short
  bottom; weights sum to zero (dollar-neutral). The output is a
  *relative-value* trade across the bond panel rather than an
  outright duration position.
* **`g10_bond_carry`** (Session 2D Commit 11) — cross-sectional but
  ranked on *carry*, not momentum. Different signal.
* **Phase 1 `bond_carry_roll`** — cross-sectional carry without
  duration adjustment. Closer in spirit to KMPV (2018).

Because this strategy is dollar-neutral by construction, its expected
ρ with `bond_tsmom_12_1` is moderate (0.5–0.8) when one bond
dominates the cross-section but lower when dispersion is concentrated
mid-curve.

## Why duration adjustment

Without adjustment, the longest-duration bond (TLT, ETF effective
duration ≈ 17) dominates the cross-sectional ranking simply because
it has the largest absolute return moves. That is a duration exposure
masquerading as a momentum signal. Adjusting the trailing return by
the bond's modified duration produces a per-unit-of-risk return
that captures *relative momentum after risk normalisation*. Durham
documents this empirically: the Sharpe of the duration-adjusted
ranking strictly exceeds the un-adjusted ranking across his test
period (1990–2015).

## Published rules (Durham §III–IV)

For each bond ``b`` and each month-end ``t``:

1. **Trailing 12-1 log return** ``r_b(t)`` over months
   ``[t−12, t−1)``.
2. **Duration adjustment:** ``s_b(t) = r_b(t) / D_b`` where ``D_b``
   is the bond's modified duration.
3. **Cross-sectional rank** at each month-end across all bonds in
   the panel. Convert ranks to dollar-neutral weights via the
   demeaned-rank-divided-by-sum-of-absolute-deviations construction.
4. **Rebalance monthly,** forward-fill to daily.

| Parameter | Default | Notes |
|---|---|---|
| `lookback_months` | `12` | 12/1 convention |
| `skip_months` | `1` | skip most-recent month |
| `durations` | see config | per-bond modified duration |

## ETF duration vs CMT duration

The default durations are **ETF effective durations**, which differ
from the *constant-maturity Treasury* durations used by the curve
strategies in this family:

| Bond proxy | ETF effective | CMT (par yield) |
|---|---|---|
| SHY (1-3Y) | 1.95 | 1.95 (close) |
| IEF (7-10Y) | 8.0 | ~8.0 (close) |
| TLT (20+Y) | 17.0 | 8.0 (10Y CMT used in curve strategies) |

The TLT mismatch is the main reason this strategy is shipped with
its own duration mapping rather than reusing the curve-strategy
durations: the curve strategies are calibrated to the 10Y CMT and
expect the long-end leg to be a 10Y proxy, whereas Durham's
cross-section spans the actual ETF basket. Using CMT durations on
ETF prices would over-weight the long-end in the rank because the
true 17-year duration of TLT translates to bigger return swings,
which dominate the rank.

For real-feed Session 2H benchmarks running on FRED constant-
maturity yields rather than ETFs, the durations should be reset to
``{"DGS2_proxy": 1.95, "DGS5_proxy": 4.5, "DGS10_proxy": 8.0}`` (or
similar CMT values) to match the input data.

## In-sample period (Durham 2015)

* Data: 1990–2015 monthly, US Treasury bond returns from CRSP
* Out-of-sample: post-2009 sub-sample shows the duration-adjusted
  signal still works post-Great-Recession
* Sharpe of the duration-adjusted long-short on 7 maturity buckets
  is ~0.6 over 1990–2015; the un-adjusted version is ~0.4. The
  ~50% Sharpe uplift from duration adjustment is the headline
  result.

## Implementation deviations from Durham (2015)

1. **Smaller bond panel** (3 ETFs vs 7 maturity buckets). With only
   3 bonds the rank dispersion is coarser and the strategy is
   noisier. Real-feed Session 2H benchmarks should expand to a
   wider FRED panel (DGS2, DGS3, DGS5, DGS7, DGS10, DGS20, DGS30)
   for a closer match to Durham's specification.
2. **Equal-weighted rank conversion** rather than the regression-
   slope sizing used in some Durham robustness checks. Equal-weight
   is the simpler and more reproducible choice.
3. **No bid-ask or short-borrow model.** Bridge applies
   ``commission_bps`` per leg.

None of these change the *direction* of the trade relative to the
paper.

## Known replications and follow-ups

* **Asness, Moskowitz, Pedersen (2013)** §V — bond TSMOM at the
  futures level; directly parallel to Durham's adjustment but on
  a different bond panel.
* **Hurst, Ooi & Pedersen (2017)** — "A Century of Evidence on
  Trend-Following Investing", AQR. Long-horizon CTA-style bond
  momentum that supports the Durham finding on a longer dataset.
