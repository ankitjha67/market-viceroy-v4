# Known failure modes — rsi_reversion_14

## 1. Trending markets

RSI(14) can stay overbought (>70) for extended periods during strong
bull trends. The strategy will be short throughout the rally. Wilder
himself noted this and recommended RSI for range-bound markets only.

## 2. Slow signal generation

14 periods smooth out noise but also delay signals. By the time
RSI(14) drops below 30, much of the selloff may have already
occurred, reducing the mean-reversion edge.

## 3. Threshold ambiguity near boundaries

RSI fluctuating near 30 or 70 creates frequent signal flips. The
strategy has no hysteresis — it enters and exits at the same level,
leading to high turnover near the thresholds.

## 4. Divergence not captured

Classical RSI analysis uses price-RSI divergences (price makes new
high but RSI doesn't). This mechanical implementation ignores
divergences and only uses absolute threshold levels.
