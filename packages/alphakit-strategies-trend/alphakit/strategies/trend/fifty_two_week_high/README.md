# fifty_two_week_high — 52-Week High Momentum (George-Hwang 2004)

> Rank stocks by `current_price / trailing_52w_high`, long top decile,
> short bottom decile, rebalance monthly.

```python
from alphakit.strategies.trend import FiftyTwoWeekHigh
from alphakit.bridges import vectorbt_bridge

strategy = FiftyTwoWeekHigh(lookback_weeks=52, top_pct=0.1)
result = vectorbt_bridge.run(strategy=strategy, prices=prices)
```

See [`paper.md`](paper.md), [`known_failures.md`](known_failures.md),
[`config.yaml`](config.yaml).
