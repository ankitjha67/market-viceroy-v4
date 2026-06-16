# Known failure modes — pairs_distance

## 1. Structural breaks

When the fundamental relationship between two assets changes
permanently (e.g., a merger, regulatory shift, or sector rotation),
the normalized spread diverges without reverting. The strategy will
hold a losing position indefinitely waiting for mean reversion that
never comes.

## 2. Pairs breaking down

Pairs selected during the formation period may lose their statistical
relationship during the trading period. The distance-based selection
does not test for economic causation, so historically close pairs
may diverge for legitimate fundamental reasons.

## 3. Crowded trade

As pairs trading became widely adopted after the GGR paper was
published, strategy returns have declined significantly. Crowding
compresses spreads and increases the probability of simultaneous
unwinding during market stress.

## 4. Lookback overfitting

The choice of formation period and Z-score lookback can be
overfit to historical data. A 252-day formation window that
happens to capture a particular regime may fail when the regime
changes. Shorter lookbacks increase noise, longer lookbacks
increase lag.
