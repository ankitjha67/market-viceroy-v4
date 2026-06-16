# Known failure modes — vol_carry_vrp

## 1. Vol spikes overwhelm carry

The VRP carry premium is small and steady, but vol spikes (e.g.,
VIX from 12 to 80 in March 2020) produce outsized losses that
dwarf months of accumulated carry. The strategy has negative
skewness and fat left tails.

## 2. Vol-of-vol risk

When volatility itself becomes volatile (vol-of-vol regimes),
the fast/slow vol spread oscillates rapidly, causing excessive
signal changes and whipsawing the position. Transaction costs
erode returns in these regimes.

## 3. Proxy doesn't capture actual VRP

The fast/slow realized vol spread is a crude approximation of
the true variance risk premium (implied minus realized). It
misses the forward-looking component entirely and can produce
false signals when the term structure of vol is flat.

## 4. Slow vol window lags regime shifts

The 20-day slow vol window is backward-looking and adapts
slowly to genuine regime changes. During a transition from
low-vol to high-vol regime, the strategy may remain long
(expecting contango) when the VRP has already turned negative.
