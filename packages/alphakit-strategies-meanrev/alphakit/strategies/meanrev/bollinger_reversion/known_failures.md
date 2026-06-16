# Known failure modes — bollinger_reversion

## 1. Trending markets

Bollinger Band reversion fails in strong trends. Price can "walk the
band" — repeatedly touching the upper band in an uptrend without ever
reverting to the SMA. The strategy will be short throughout the trend.

## 2. Volatility regime shifts

A sudden increase in volatility widens the bands, which means the
strategy may miss the initial move. Conversely, a volatility crush
narrows the bands, generating false signals during the squeeze.

## 3. Fat tails

The ±2σ thresholds assume roughly normal returns. Real asset returns
have fat tails, so extreme moves beyond the bands occur more often
than expected. The strategy can accumulate large losses if price
moves far past the band without reverting.

## 4. Mean-reversion horizon mismatch

The 20-day SMA defines a ~1-month mean-reversion horizon. Assets
that mean-revert on longer or shorter timescales will not be well
served by this parameterization.
