# Known failure modes — yield_curve_pca_trade

> PCA-residual strategies are *quiet alpha*: small per-trade
> realisations, modest Sharpe, but very low correlations to other
> factor strategies. They fail when the PCA fit is unstable
> (regime change, data gaps) or when the residuals stop being
> mean-reverting.

Cross-sectional dollar-neutral mean-reversion on PCA residuals.
Will lose money in the regimes below.

## 1. Regime change inside the PCA fit window (2008-09, 2020 Q1, 2022)

The rolling PCA fit on 24 months is sensitive to data points from
two different regimes. When a regime change occurs, the fit window
straddles both regimes and the eigendecomposition becomes unstable:
small changes to the input can flip the sign or rotate the top
eigenvectors. The "residual" then becomes a function of the
covariance instability rather than genuine idiosyncratic
deviation.

Expected behaviour at a regime change point:

* Eigenvectors flip-rotate over a few months
* "Residual" signs invert randomly during the rotation
* Strategy whipsaws for 6-12 months until the rolling window has
  fully transitioned to the new regime
* Drawdown of 5-10% during the rotation period

Mitigation: switch from PCA to a more stable factor model (e.g.
Nelson-Siegel parametric) during high-volatility regimes. Phase 3
candidate.

## 2. PCA over-fit on small panels (N=5)

With only 5 bonds in the panel, PCA on 24 monthly observations is
borderline-stable: 24 observations × 5 features = 120 data points,
but the 5x5 covariance matrix has 15 unique parameters. Estimation
error is non-trivial, especially in the lower eigenvalues.

The strategy uses ``np.linalg.eigh`` for the symmetric
eigendecomposition, which is numerically stable, but the *sample*
covariance underlying the decomposition is itself noisy at this
panel size.

Mitigation: expand to wider panel (FRED DGS2/3/5/7/10/20/30 = 7
yields) for Session 2H real-feed benchmarks. With N=7, the
covariance has 28 parameters and 24 observations gives 168 data
points — better but still close to the asymptotic regime.

## 3. Residual is *not* mean-reverting in stress

Litterman/Scheinkman document mean-reversion under *normal* market
conditions. During liquidity stress (2008 Q4, 2020 March), the
residual can persist or even widen further as illiquid bonds
trade away from fair value. The strategy enters a long-cheap /
short-rich position assuming mean-reversion, but the cheap bond
gets cheaper and the rich bond gets richer — a classic LTCM-style
loss.

Symbolic example (2008 Q4): on-the-run TLT trades rich vs older
cohorts as flight-to-quality concentrates demand. The residual
on TLT is highly positive; the strategy shorts TLT. Then TLT
rallies *more* as the safe-haven bid intensifies, costing the
strategy.

## 4. Cluster correlation with sibling strategies

* `curve_butterfly_2s5s10s` — same factor (PC3) on a sub-panel.
  Expected ρ ≈ 0.6-0.8 when the 5Y residual dominates the rank.
* `bond_tsmom_12_1` and `real_yield_momentum` — momentum vs
  mean-reversion are typically negatively correlated; expected ρ
  ≈ −0.2 to 0.0.
* `bond_carry_rolldown` — outright duration; orthogonal to
  PCA-residual cross-section by construction; expected ρ ≈ 0.

The negative correlation with momentum is intentional: this
strategy is meant to be a complement to the trend-following sleeve.

## 5. Computational cost

The rolling PCA is O(N²) per month-end (eigendecomposition of an
N×N matrix). With N=5 and 250 month-ends over the OOS window,
this is fast (<1s). With N=30 and daily rebalance the cost grows
substantially. The strategy enforces monthly rebalance to keep
the cost manageable.

## 6. Interpretation drift

The "level / slope / curvature" interpretation of PC1/PC2/PC3 holds
only in normal regimes. During flight-to-quality the eigenvectors
re-orient (level may load more on the long-end than uniformly;
slope may rotate). The strategy doesn't depend on the
interpretation — it just trades the residual after stripping the
top-3 PCs — but a user expecting the PCA factors to map to
"level/slope/curvature" may be surprised.

## Regime performance (reference, gross of fees, 5-bond cross-sectional residual)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Normal regime (2003-07) | 2003-01 – 2007-06 | ~0.6 | −3% |
| GFC (2008-09) | 2008-09 – 2009-12 | ~−0.4 | −9% |
| QE-supported normalisation (2010-14) | 2010-2014 | ~0.4 | −5% |
| 2020 March COVID dislocation | 2020-03 – 2020-06 | ~−0.6 | −7% |
| 2021-22 inflation regime shift | 2021-06 – 2022-12 | ~−0.3 | −10% |
| 2023-25 normalisation | 2023-2025 | ~0.5 | −4% |

(Reference ranges from Litterman/Scheinkman replication papers;
the in-repo benchmark is authoritative for this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
