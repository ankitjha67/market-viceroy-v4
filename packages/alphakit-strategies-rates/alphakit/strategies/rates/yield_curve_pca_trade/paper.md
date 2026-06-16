# Paper — Yield-Curve PCA Trade (Litterman/Scheinkman 1991)

## Citation

**Foundational and primary methodology:** Litterman, R. & Scheinkman, J.
(1991). **Common factors affecting bond returns.** *Journal of Fixed
Income*, 1(1), 54–61.
[https://doi.org/10.3905/jfi.1991.692347](https://doi.org/10.3905/jfi.1991.692347)

BibTeX entry: `littermanScheinkman1991` (already in
`docs/papers/phase-2.bib`, added by `curve_steepener_2s10s` in
Commit 3).

## Why a single citation

The mean-reversion-on-PCA-residual rule follows mechanically from
the Litterman/Scheinkman PCA decomposition: the top 3 PCs explain
roughly 99% of yield-curve variance and are the canonical priced
risk factors (level, slope, curvature). Anything *unexplained* by
those 3 factors is by definition idiosyncratic and mean-reverting
toward zero; trading the residual is the canonical way to harvest
the noise. No separate expected-return paper is required.

## Differentiation from `curve_butterfly_2s5s10s`

* **`curve_butterfly_2s5s10s`** — fixed-weight ½/−1/½ proxy for PC3
  on a specific 2-5-10Y triplet. Simpler signal, deterministic
  weights, smaller portfolio (3 bonds).
* **`yield_curve_pca_trade`** (this strategy) — full rolling PCA
  fit on an N-bond panel, trades the residual *after* the top 3
  PCs. The signal isolates strictly idiosyncratic deviations across
  all bonds, not just curvature.

The two strategies overlap when the 5Y bond's idiosyncratic residual
is large; expected ρ ≈ 0.6-0.8. They are partial overlaps, not
duplicates: the PCA strategy captures residuals on *all* bonds while
the butterfly captures only the 2-5-10 curvature.

## Algorithm

For each month-end ``t``:

1. **Trailing window** of monthly log returns over the past
   ``pca_window_months`` months (default 24). Shape:
   ``(window, n_assets)``.
2. **De-mean** column-wise.
3. **Covariance** of the de-meaned returns.
4. **Eigendecomposition** via ``numpy.linalg.eigh`` — symmetric
   eigendecomposition gives real eigenvalues and orthonormal
   eigenvectors. Take the top ``n_pcs`` eigenvectors.
5. **Reconstruct** the most recent monthly return from the top PCs::

       scores = top_eigvecs.T @ current_demeaned   # shape (n_pcs,)
       reconstructed = top_eigvecs @ scores         # shape (n_assets,)

6. **Residual** = ``current_demeaned − reconstructed``.
7. **Rolling residual sum** over ``residual_lookback_months``
   (default 3) — accumulates idiosyncratic deviation over recent
   months while not being so stale that mean-reversion has already
   realised.
8. **Cross-sectional rank** of the rolling residual sum, descending.
   Convert to dollar-neutral mean-reversion weights via the
   demeaned-rank construction. Sign is **negative**: short the
   bond with the most positive rolling residual (over-extended →
   expect mean-reversion downward), long the bond with the most
   negative rolling residual.
9. **Forward-fill** monthly weights to daily.

| Parameter | Default | Notes |
|---|---|---|
| `n_pcs` | `3` | level, slope, curvature |
| `pca_window_months` | `24` | 2-year fit window |
| `residual_lookback_months` | `3` | accumulate residuals over 3 months |

## Why these defaults

* **`n_pcs = 3`**: matches Litterman/Scheinkman's empirical finding
  that 3 PCs explain ~99% of yield-curve variance. Higher values
  capture noise; lower values leave the slope/curvature in the
  residual (defeating the strategy).
* **`pca_window_months = 24`**: enough degrees of freedom (24
  observations on N=5 assets is well-determined) while remaining
  reactive to regime change. Shorter windows over-fit to recent
  noise; longer windows under-react to regime change.
* **`residual_lookback_months = 3`**: residuals are noisy month-to-
  month, but the 3-month accumulation is a balance between signal
  strength and realisation latency. Durham (2015) §III uses
  similar 3-month accumulation for related cross-sectional rate
  signals.

## In-sample period (Litterman/Scheinkman 1991)

* Data: 1984–1988 monthly Treasury returns (the original CRSP
  zero-coupon files)
* The PC3 (curvature) factor is *both* mean-reverting and a priced
  risk factor; trading its deviations should earn the priced
  premium plus the mean-reversion component.

## Implementation deviations from Litterman/Scheinkman

1. **Rolling PCA** instead of single-period PCA. The original paper
   fits PCA once on a long historical window; this implementation
   re-fits each month for reactivity.
2. **Cross-sectional rank** instead of fitting a regression to the
   residual time series. Rank-based weighting is robust to
   outliers and avoids re-fitting a regression on the residual.
3. **No transaction-cost or short-borrow model** beyond the bridge's
   ``commission_bps`` parameter.

## Known replications and follow-ups

* **Diebold & Li (2006)** — three-factor Nelson-Siegel decomposition
  of the curve with explicit factor dynamics; alternative to PCA
  with similar economic content.
* **Bowsher & Meeks (2008)** — refined factor dynamics for the
  yield curve including regime-switching estimates.
