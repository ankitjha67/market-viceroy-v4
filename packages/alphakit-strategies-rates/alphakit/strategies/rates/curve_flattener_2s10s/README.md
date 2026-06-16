# curve_flattener_2s10s — 2s10s Curve Flattener

DV01-neutral 2s10s flattener with z-score entry/exit hysteresis on
the log-price spread. Mirror image of
[`curve_steepener_2s10s`](../curve_steepener_2s10s/README.md). Same
academic anchors: Litterman/Scheinkman (1991) for slope-as-stationary-
factor, Cochrane/Piazzesi (2005) for slope-predicts-excess-returns.

> Long the long-end / short the short-end when the long-end has
> under-performed by ≥1σ over the trailing year (yield spread is wide
> vs history). Exit when the spread normalises within 0.25σ.
> DV01-neutral by default duration ratio 8.0 / 1.95.

## Quickstart

```python
from alphakit.strategies.rates import CurveFlattener2s10s
from alphakit.bridges import vectorbt_bridge
import pandas as pd

prices: pd.DataFrame = ...   # 2 cols: short-end first, long-end second

strategy = CurveFlattener2s10s()
result = vectorbt_bridge.run(
    strategy=strategy,
    prices=prices,
    initial_cash=100_000,
    commission_bps=2,
)
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `zscore_window` | `252` | Trailing window for z-score (≈ 1 year) |
| `entry_threshold` | `1.0` σ | Enter when log-price spread is ≥1σ below mean |
| `exit_threshold` | `0.25` σ | Exit when z-score crosses back above −0.25σ |
| `long_duration` | `8.0` | Modified duration of long-end leg |
| `short_duration` | `1.95` | Modified duration of short-end leg |

See [`config.yaml`](config.yaml), [`strategy.py`](strategy.py),
[`paper.md`](paper.md), and [`known_failures.md`](known_failures.md).

The flattener and steepener are mirror images by construction
(expected ρ ≈ −1.0). Never run both at the same time.
