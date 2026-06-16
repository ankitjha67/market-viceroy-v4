# Known failure modes — fifty_two_week_high

## 1. Sharp bear markets

When every stock is far from its 52-week high (e.g. 2008, 2020 Q1),
the top decile is still "the least bad" of a bad bunch. The ranking
is still meaningful but the long side can deliver large absolute
losses. Not a bug — just know the strategy does not protect against
systematic market drawdowns.

## 2. Anchoring inversion during rapid rallies

In the first few months after a major bottom, the stocks closest to
their 52-week high are often *the same ones* that had been near
their highs at the top of the old bull market — precisely the names
that have the *least* snap-back rally. The strategy lags for 3–6
months after major regime changes.

## 3. Momentum crashes shared with all trend-following signals

2009 momentum crash. 2016 factor rotation. 2020 recovery whipsaw.
Same failure mode as `xs_momentum_jt`.

## 4. Small universes

With 5–10 symbols the ranks coarsen and the long/short edges disappear
— one ETF hits its 52w high and owns the whole long book.
