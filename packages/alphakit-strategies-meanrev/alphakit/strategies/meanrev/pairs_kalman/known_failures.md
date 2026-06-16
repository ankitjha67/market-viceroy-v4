# Known failure modes — pairs_kalman

## 1. Kalman filter initialization sensitivity

The initial state (beta=0, covariance=1) may be far from the true
hedge ratio, causing poor spread estimates during the early burn-in
period. If the initial uncertainty is set too low, the filter adapts
slowly; too high and it over-reacts to early observations.

## 2. Model misspecification

The Kalman filter assumes the hedge ratio follows a random walk and
that observation noise is Gaussian with known variance. Real hedge
ratios may jump discontinuously during regime changes, and residuals
often exhibit fat tails, violating these assumptions.

## 3. Computational overhead

The Kalman filter runs sequentially (cannot be vectorized across
time), making it significantly slower than rolling-window approaches
for large universes with many pairs. For N assets, the O(N^2) pair
enumeration compounds this cost.

## 4. Overfitting filter parameters

The delta and ve parameters control the filter's responsiveness.
These are typically set by trial and error rather than estimated from
data, creating a risk of overfitting to in-sample performance. Small
changes in delta can dramatically alter the trading signals.
