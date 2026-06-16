# dual_momentum_gem — Global Equities Momentum (Antonacci 2014)

> Check US-equity 12-month return against T-bills (absolute momentum).
> If it passes, pick the higher of US / International equity
> (relative momentum). Otherwise hold bonds. 100% one asset, rebalance monthly.

## Quickstart

```python
from alphakit.strategies.trend import DualMomentumGEM
from alphakit.bridges import vectorbt_bridge
import pandas as pd

prices: pd.DataFrame = ...  # must contain SPY, VEU, AGG, SHY columns
strategy = DualMomentumGEM()
result = vectorbt_bridge.run(strategy=strategy, prices=prices)
print(f"Sharpe: {result.metrics['sharpe']:.2f}")
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `us_equity` | `"SPY"` | US equity ticker |
| `intl_equity` | `"VEU"` | International equity ticker |
| `bonds` | `"AGG"` | Bond ticker |
| `risk_free` | `"SHY"` | Risk-free (short-Treasury) ticker |
| `lookback_months` | `12` | Lookback for both absolute and relative momentum |

See [`paper.md`](paper.md), [`known_failures.md`](known_failures.md),
[`config.yaml`](config.yaml).
