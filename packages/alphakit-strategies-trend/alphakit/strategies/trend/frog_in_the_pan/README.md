# frog_in_the_pan — Continuity-Weighted Cross-Sectional Momentum

> Rank stocks by `cumulative_return × (1 − |ID|)` where ID is the
> information-discreteness measure of Da, Gurun & Warachka (2014).
> Long top decile, short bottom decile, monthly rebalance.

## Quickstart

```python
from alphakit.strategies.trend import FrogInThePan
from alphakit.bridges import vectorbt_bridge
import pandas as pd

prices: pd.DataFrame = ...
strategy = FrogInThePan()
result = vectorbt_bridge.run(strategy=strategy, prices=prices)
```

## Parameters

Same shape as `xs_momentum_jt`: `formation_months`, `skip_months`,
`top_pct`, `long_only`, `min_positions_per_side`.

See [`paper.md`](paper.md), [`known_failures.md`](known_failures.md),
[`config.yaml`](config.yaml).
