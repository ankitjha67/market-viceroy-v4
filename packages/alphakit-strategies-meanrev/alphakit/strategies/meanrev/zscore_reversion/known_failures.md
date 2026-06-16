# Known failure modes — zscore_reversion

## 1. Structural breaks

The Z-score assumes the rolling mean is stable. A structural break
(earnings surprise, M&A, sector rotation) shifts the mean permanently
and the Z-score signal becomes stale.

## 2. Non-stationary volatility

The rolling σ adapts slowly. A sudden volatility spike widens the
effective bands, but the lookback window smooths the effect, leading
to delayed signal generation.

## 3. Same failure as Bollinger bands

The Z-score approach is mathematically equivalent to Bollinger bands
with the same lookback. It inherits all Bollinger band failure modes.

## 4. Lookback sensitivity

Short lookbacks (10-15 days) produce noisy signals; long lookbacks
(50+ days) are slow to react. The 20-day default is a compromise
with no strong theoretical justification.
