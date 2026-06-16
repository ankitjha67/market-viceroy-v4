# curve_steepener_2s10s — 2s10s Curve Steepener

DV01-neutral 2s10s steepener with z-score entry/exit hysteresis on
the log-price spread. Anchored on Litterman/Scheinkman (1991) for
the slope-as-stationary-factor justification and Cochrane/Piazzesi
(2005) for the slope-predicts-excess-returns justification.

> Long the short-end / short the long-end when the long-end has
> outperformed by ≥1σ over the trailing year (yield spread is narrow
> vs history). Exit when the spread normalises within 0.25σ.
> DV01-neutral by default duration ratio 8.0 / 1.95.

## Quickstart

```python
from alphakit.strategies.rates import CurveSteepener2s10s
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# 2-column price panel: short-end first, long-end second.
prices: pd.DataFrame = ...   # columns ["SHY", "TLT"]

strategy = CurveSteepener2s10s()
result = vectorbt_bridge.run(
    strategy=strategy,
    prices=prices,
    initial_cash=100_000,
    commission_bps=2,
)

print(f"Sharpe: {result.sharpe:.2f}")
print(f"Max DD: {result.max_dd:.1%}")
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `zscore_window` | `252` | Trailing window for z-score (≈ 1 year) |
| `entry_threshold` | `1.0` σ | Enter when log-price spread is ≥1σ above mean |
| `exit_threshold` | `0.25` σ | Exit when z-score crosses back below 0.25σ |
| `long_duration` | `8.0` | Modified duration of long-end leg |
| `short_duration` | `1.95` | Modified duration of short-end leg |

See [`config.yaml`](config.yaml) for the full default configuration
and [`strategy.py`](strategy.py) for the implementation docstring.

## Documentation

* [Foundational + primary citations](paper.md) — Litterman/Scheinkman
  (1991) for the slope-as-stationary-factor result and
  Cochrane/Piazzesi (2005) for the slope-predicts-excess-returns
  result
* [Known failure modes](known_failures.md) — persistent inversion
  (1998–2000, 2006–2007, 2022–2024), carry burn during normal
  regimes, imperfect DV01 neutrality, ETF basket drift, cluster
  correlation with the flattener / butterfly siblings, single-pair
  concentration risk
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed benchmark deferred to Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-rates/alphakit/strategies/rates/curve_steepener_2s10s/tests
```
