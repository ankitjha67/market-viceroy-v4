# Known failure modes — long_term_reversal

## 1. Momentum crashes

During sharp market reversals (e.g., 2009 rebound), long-term
losers can continue to underperform if their decline was driven
by fundamental deterioration rather than overreaction. The strategy
cannot distinguish between overreaction and justified re-pricing.

## 2. Survivorship bias sensitivity

The original study used NYSE-listed stocks. In live trading, many
extreme losers delist or go bankrupt. Without proper handling of
delisted securities, the strategy overstates returns from the
loser portfolio.

## 3. Slow convergence

The 3-year lookback creates very long warmup periods. With monthly
rebalancing, the strategy requires at least 3 years of data before
generating any signals. In short evaluation windows this produces
a large fraction of zero-weight bars.

## 4. Crowding in value factor

Long-term reversal is highly correlated with the value factor
(HML). During periods when value underperforms (e.g., 2017-2020
growth dominance), the strategy suffers extended drawdowns.
