# Known failure modes — rsi_reversion_2

## 1. Trend persistence

In strong directional moves (crash or melt-up), RSI(2) can stay
extreme for multiple consecutive days. Buying at RSI(2) < 10 during
a multi-day waterfall decline means catching a falling knife.

## 2. Regime dependence

Connors' original test period (1995-2007) was a largely bullish,
mean-reverting regime. Post-2008 markets show more momentum and
fat-tail behavior where 2-day reversals are less reliable.

## 3. Capacity constraints

The 2-period window means signals are extremely short-lived (1-2
days). High turnover and tight windows limit practical capacity.

## 4. Gap risk

The strategy fires at end-of-day RSI levels. Overnight gaps can
move prices significantly before the next trading session, eroding
expected edge.
