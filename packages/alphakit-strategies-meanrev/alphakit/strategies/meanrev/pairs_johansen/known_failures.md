# Known failure modes — pairs_johansen

## 1. Small sample eigendecomposition noise

With a 252-day window and multiple assets, the covariance matrix
may be poorly conditioned, leading to noisy eigenvector estimates.

## 2. Eigenvector instability

Rolling eigenvectors can flip sign between windows, causing spurious
position reversals. This implementation normalizes by absolute value
but cannot prevent rotational instability.

## 3. Regime changes

Cointegrating relationships can break down during regime changes
(e.g., crisis periods when correlations spike). The spread may
diverge permanently.

## 4. Computational cost

Eigendecomposition per rolling window per bar is O(T * N^3) where
N is the number of assets.
