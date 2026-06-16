# sma_cross_10_30 — 10/30 SMA Crossover (Brock-Lakonishok-LeBaron 1992)

> Long each asset when its 10-day SMA crosses above its 30-day SMA,
> short when it crosses below. Per-asset weight is
> `sign(fast − slow) / n_symbols`.

```python
from alphakit.strategies.trend import SMACross1030
from alphakit.bridges import vectorbt_bridge

result = vectorbt_bridge.run(strategy=SMACross1030(), prices=prices)
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `fast_window` | `10` | fast SMA period |
| `slow_window` | `30` | slow SMA period |
| `long_only` | `False` | collapse shorts into flat |

See [`paper.md`](paper.md), [`known_failures.md`](known_failures.md).
