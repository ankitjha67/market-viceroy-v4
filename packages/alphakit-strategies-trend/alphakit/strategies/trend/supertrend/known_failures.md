# Known failure modes — supertrend

## 1. No academic validation

Unlike BLL (1992) for SMA crosses or Donchian (1960) for breakouts,
Supertrend has no published in-sample test. The default parameters
(``period=10, multiplier=3``) are practitioner folklore. Treat any
in-sample Sharpe with extra scepticism.

## 2. Close-only ATR approximation

Wilder's original ATR uses high, low and the previous close. AlphaKit
uses close-only data so the ATR is proxied by ``|close[t] − close[t-1]|``.
This understates true range on wide-range days and the band width is
narrower than a full-OHLC implementation.

## 3. Whipsaws on volatility expansions

A sudden vol spike widens the bands and can cause the strategy to
exit a trend just as it's about to continue. The 2022 bond selloff
is a good example — Supertrend flipped short bonds just before the
price action re-stabilised and the new rate regime solidified.

## 4. Multiplier sensitivity

Changing the multiplier from 3 to 2 roughly doubles the number of
state flips. Users should keep the multiplier fixed across a
backtest rather than optimise it in-sample.
