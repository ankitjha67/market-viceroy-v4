# Known failure modes — gap_fill

## 1. Trending markets with persistent gaps

In strong trends (e.g., momentum-driven rallies or crashes), gaps
in the direction of the trend are not mean-reverting. The strategy
will fade each gap and accumulate losses as price continues to move
away from the prior close.

## 2. Low-volatility regimes

When realized volatility is very low, the rolling standard deviation
shrinks, making the Z-score threshold easier to breach on even modest
moves. This generates spurious signals that erode returns through
transaction costs and whipsaw.

## 3. Event-driven gaps

Gaps caused by earnings announcements, central bank decisions, or
other fundamental events often do not fill. The new information
permanently shifts the price level, and the strategy incorrectly
bets on reversion.

## 4. Close-only price approximation

The original gap fill concept uses open prices to define the gap.
This implementation approximates the gap from daily returns (close
to close), which blends overnight and intraday moves and dilutes
the signal.
