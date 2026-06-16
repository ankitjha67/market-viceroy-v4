# Known failure modes — ema_cross_12_26

## 1. Whipsaws in choppy markets

Same failure mode as every moving-average cross. The EMA's higher
weight on recent data makes it slightly less prone to whipsaws than
SMA(10)/SMA(30), but only marginally.

## 2. Noise sensitivity

EMAs respond to large single-day moves harder than SMAs because the
alpha weight of the most recent bar is ~15% for a 12-span EMA. A
single outlier day can flip the cross.

## 3. No academic bootstrap

Unlike BLL (1992) for SMA crosses, the 12/26 EMA parameters do not
have a formal academic validation. They are chosen by practitioner
convention, which means:
* In-sample bias is unknown (and probably large).
* Out-of-sample Sharpe estimates should be interpreted with caution.

## 4. Same-direction "hedged" assets

When the universe contains both the index and its inverse (e.g. SPY
and SH), the strategy's per-asset convention means you're essentially
doubling the equity bet in one direction whenever the indicators
agree. Use a long-only universe for this strategy.
