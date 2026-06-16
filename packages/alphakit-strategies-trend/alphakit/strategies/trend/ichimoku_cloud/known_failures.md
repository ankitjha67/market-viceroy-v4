# Known failure modes — ichimoku_cloud

## 1. Long warm-up

The cloud needs 52 + 26 = 78 bars of history before Senkou Span B
can be projected. Expect 3+ months of zero weights before the signal
becomes active.

## 2. Flat signal inside the cloud

When price is inside the cloud (between Senkou A and Senkou B) the
signal is zero — the strategy sits out these ranges by design. This
is both a feature (avoids choppy periods) and a cost (misses the
early stages of a new trend while price traverses the cloud).

## 3. Close-only approximation

Using rolling max/min of close instead of OHLC high/low slightly
biases the cloud edges on high-volatility sessions. The sign of the
signal is right ~95% of the time on daily bars but the cloud
thickness is understated.

## 4. Practitioner tradition, not academic evidence

There is no peer-reviewed academic study that isolates Ichimoku alpha
from simpler moving-average alternatives. Expected out-of-sample
Sharpe is comparable to `sma_cross_10_30` — the cloud does not
magically outperform its constituent moving averages.
