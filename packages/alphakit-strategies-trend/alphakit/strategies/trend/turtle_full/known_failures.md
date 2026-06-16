# Known failure modes — turtle_full

## 1. Simplified sizing

Without ATR-based units, low-vol assets get the same weight as high-vol
assets. Drawdowns on AGG-like instruments will be muted relative to a
correct Turtle implementation, and commodities will swing wider.

## 2. No correlation caps

When energy, metals and grains all break out together, the combined
long is four-times one sector's native risk, vs the real Turtle cap.
In the 2008 commodity blow-off this would have concentrated risk.

## 3. Drawdown pain during regime transitions

Every trend system pays during regime changes. The Turtles reported
30-50% peak-to-trough drawdowns during flat years (1985, 1987 late).
Expect similar on this strategy during 2018, 2022 H1, 2023 Q1.

## 4. Public-rule fade

Since Faith's book went public in 2003, the specific 20/10 and 55/20
parameters have degraded. Out-of-sample Sharpe on futures panels is
typically 0.3-0.5, vs 1.0+ in the pre-publication Turtle years.
