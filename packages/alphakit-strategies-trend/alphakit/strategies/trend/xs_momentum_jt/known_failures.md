# Known failure modes — xs_momentum_jt

## 1. Momentum crashes (2009)

The canonical momentum crash. After a sharp market bottom the
*yesterday's losers* become *today's winners*, and the short side
blows up. Daniel & Moskowitz (2016) document March–May 2009 as the
worst 3-month drawdown for the cross-sectional momentum factor in
history — down roughly 40–70% depending on exact construction.

Expected behaviour in any post-crisis rebound:
* Deep, fast drawdown on the short side
* Slow recovery (6–12 months)

## 2. Small universes

With fewer than ~20 instruments the top/bottom decile rounds to 1
name each, and single-name idiosyncratic moves dominate the factor.
`min_positions_per_side` keeps the strategy defined but the economic
signal degrades.

## 3. Rotation lag

Because the formation window is 6 months with a 1-month skip, the
strategy holds losers for ~6 months into a regime change. This is
the source of 2023 underperformance as well — the SVB shock flipped
winners/losers faster than the strategy could react.

## 4. Equity-only

The paper and this implementation are equity-specific; feeding it
futures or FX produces nonsense because the long/short decile
construction does not transfer cleanly to those asset classes. Use
`tsmom_12_1` or `tsmom_volscaled` for multi-asset trend.
