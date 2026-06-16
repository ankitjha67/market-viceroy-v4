# Known failure modes — curve_butterfly_2s5s10s

> The butterfly is the canonical PC3 trade. PC3 explains only ~5%
> of yield variance, so the trade has **lower** absolute returns
> than slope or level trades but also **lower** correlations to
> them — it is a small-but-uncorrelated alpha source rather than a
> large-but-overlapping one.

DV01-weighted 2s5s10s butterfly with z-score entry/exit hysteresis
on a price-space curvature proxy. Trades mean-reversion in both
directions (short-belly when belly is rich, long-belly when belly
is cheap). The strategy will lose money in the regimes below.

## 1. Persistent curvature regime change (e.g. quantitative easing 2010–2014)

Federal Reserve large-scale asset purchases (QE) of belly-and-back
maturities can drive the 5Y yield significantly below the 2-10
linear interpolation for sustained periods (the 5Y becomes
*persistently rich*). The strategy enters the short-belly butterfly,
expecting the belly to cheapen, but the belly stays rich for the
duration of the QE program. Drawdowns in this regime can reach 8–12%
of NAV before mean-reversion finally arrives.

Symmetrically: aggressive Fed selling at the belly (e.g. Operation
Twist's belly-cheapening leg) drives the 5Y unusually cheap and
keeps it there. The long-belly butterfly bleeds for months.

Mitigation: tighten ``entry_threshold`` to 1.5σ during known
QE/QT regimes, accepting fewer trades for higher conviction.

## 2. Belly proxy duration mismatch (real-data only)

The default ETF universe uses **IEF as the belly**, but IEF is a
7-10 Year Treasury Bond ETF with effective duration ≈ 8 years —
much closer to TLT (long wing) than to a true 5Y. With IEF as
belly:

* The price-space ``fly_price`` proxy is contaminated by 7-10Y
  cash-flow exposure that *should* be in the long-end leg.
* DV01-weighting using ``belly_duration = 4.5`` over-allocates the
  wings (because the actual belly duration is 8, the wings should
  carry more DV01 to offset).

The synthetic-fixture benchmark uses IEF and is therefore biased.
Real-feed Session 2H runs should:

* Construct a 5Y-equivalent series from FRED's `DGS5` via the
  duration approximation (matching the other curve strategies in
  this family), or
* Use a 50/50 SHY+IEF mix as the belly proxy and document the
  duration in `meta.belly_duration`.

This caveat is the single biggest contributor to the gap between
the synthetic and real-data benchmarks for this strategy.

## 3. Imperfect DV01 neutrality

The default duration triplet (1.95 / 4.5 / 8.0) is the par-yield
ratio of constant-maturity 2Y / 5Y / 10Y Treasuries. Actual
durations drift with the yield level; at 1% par yield the durations
become approximately 1.97 / 4.85 / 9.10, changing the DV01-balanced
weights by 8–15%. In a 50 bps parallel rally the residual exposure
biases P&L by ±10–15 bps per unit of signal — small but non-zero.

## 4. Cluster correlation with sibling rates strategies

* `yield_curve_pca_trade` — explicit PCA-driven curvature trade;
  expected ρ ≈ 0.6–0.8. The two strategies trade the same factor;
  the butterfly is the simpler price-space proxy and the PCA
  variant is the loadings-driven version.
* `curve_steepener_2s10s` and `curve_flattener_2s10s` — slope
  trades that are *DV01-orthogonal* to the curvature trade by
  construction, but the orthogonality is approximate (not exact)
  due to the price-space proxy. Expected ρ ≈ 0.3–0.5 in regimes
  where slope and curvature co-move.

The sibling-overlap profile is unusual for the family: the
butterfly is closer to the PCA strategy (same factor, different
implementation) than to the slope strategies (different factor).
Phase 2 master plan §10 cluster-risk acceptance bar: ρ > 0.95
triggers deduplication review; the expected 0.6–0.8 with the PCA
strategy is borderline-acceptable and will be re-examined in
Session 2H once the real-feed benchmark for both lands.

## 5. Low-Sharpe regime in calm curvature environments

When PC3 has compressed dispersion (e.g. 2014–2017, 2024–2025),
the z-score rarely crosses ±1.0σ and the strategy stays out for
months. This is *not* a failure — the strategy correctly waits for
opportunities — but users sizing the strategy by recent Sharpe will
under-allocate after compressed-dispersion periods just as
opportunities re-emerge.

Mitigation: size the butterfly by long-run vol-of-Sharpe rather
than trailing 1Y Sharpe. Phase 2 master plan §10 covers the
vol-of-Sharpe metric in the cluster-correlation analysis.

## 6. Non-stationarity at extreme yield levels

Below 0% and above 8% par yield the duration-bias and price-space
proxy assumptions break down significantly:

* At deeply negative yields (Europe 2014–2022) the proxy is sign-
  ambiguous because log-prices are bounded.
* At very high yields (US 1981, 2022 for short-end) the convexity
  contribution to the price proxy is no longer negligible vs the
  duration term.

This strategy is calibrated for the 0–8% USD yield regime. Outside
that range the `paper.md` approximations cease to hold and a re-fit
PCA implementation is required.

## Regime performance (reference, gross of fees, DV01-weighted 2s5s10s butterfly)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| QE-driven curvature distortion (2010–2014) | 2010-09 – 2014-12 | ~−0.4 | −10% |
| Curvature normalisation (2015–2017) | 2015-01 – 2017-12 | ~0.7 | −4% |
| Operation Twist (2011–2012) | 2011-09 – 2012-12 | ~−0.6 | −7% |
| 2022 inversion year | 2022-01 – 2022-12 | ~0.3 | −5% |

(Reference ranges from CTA-reported butterfly sleeves and from
academic papers on PC3 dynamics; the in-repo benchmark is the
authoritative source for this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
