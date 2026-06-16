# Known failure modes — donchian_breakout_20

## 1. Whipsaws in range-bound markets

The 20-day window is aggressive and flips frequently when prices
oscillate within a range. Each whipsaw is a ~1-3% drawdown.

## 2. False breakouts during low-volume periods

Thin-market false breakouts (e.g. holiday-thin sessions, after-hours
on crypto) can fire the signal and reverse within a day. The
per-bar state machine locks in the position regardless.

## 3. Late entries on trending assets

The 20-day window is short, so entries happen relatively quickly —
but on strongly trending assets the breakout level is already 2-3%
above where a moving-average cross would have fired.
