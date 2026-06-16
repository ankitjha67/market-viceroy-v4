# Known failure modes — ou_process_trade

## 1. Non-stationary series

OU calibration assumes the underlying process is stationary. If the
asset is trending (non-mean-reverting), the OLS regression yields
a positive slope (b >= 0) and the strategy correctly abstains — but
it misses the trend.

## 2. Short calibration window

A 60-day window provides limited statistical power for OU parameter
estimation. The half-life estimate can be noisy, especially when
the true OU parameters are time-varying.

## 3. Computational cost

Unlike vectorized Z-score or Bollinger bands, OU calibration requires
a per-asset, per-bar OLS regression. This is O(T * N * lookback)
which can be slow for large universes.

## 4. Log-price assumption

The strategy calibrates on log-prices. This is correct for geometric
OU processes but may not capture all mean-reversion dynamics in
level-space.
