# xs_momentum_jt — Cross-Sectional Momentum (Jegadeesh-Titman 1993)

> Rank equities by their 6-month return (skipping the most recent month),
> go long the top decile and short the bottom decile, rebalance monthly.

## Quickstart

```python
from alphakit.strategies.trend import CrossSectionalMomentumJT
from alphakit.bridges import vectorbt_bridge
import pandas as pd

prices: pd.DataFrame = ...  # equity panel, DatetimeIndex, >= 10 symbols
strategy = CrossSectionalMomentumJT(formation_months=6, top_pct=0.1)
result = vectorbt_bridge.run(strategy=strategy, prices=prices)
print(f"Sharpe: {result.metrics['sharpe']:.2f}")
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `formation_months` | `6` | trailing window for the ranking |
| `skip_months` | `1` | most-recent months to skip |
| `top_pct` | `0.1` | long/short decile fraction |
| `long_only` | `False` | drop the short side |
| `min_positions_per_side` | `1` | floor for small universes |

See [`paper.md`](paper.md), [`known_failures.md`](known_failures.md),
and [`config.yaml`](config.yaml).
