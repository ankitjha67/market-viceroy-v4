# curve_butterfly_2s5s10s — 2s5s10s Curve Butterfly (PC3)

DV01-weighted 2s5s10s butterfly with z-score entry/exit hysteresis
on a price-space curvature proxy. Trades mean-reversion of the third
principal component of the yield curve in both directions.

> Long wings / short belly when belly is rich (z > +1σ); short wings /
> long belly when belly is cheap (z < −1σ). DV01-weighted by default
> durations 1.95 / 4.5 / 8.0.

## Quickstart

```python
from alphakit.strategies.rates import CurveButterfly2s5s10s
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# 3-column price panel: [short_end, belly, long_end].
prices: pd.DataFrame = ...   # e.g. ["SHY", "IEF", "TLT"]

strategy = CurveButterfly2s5s10s()
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
| `zscore_window` | `252` | Trailing window for z-score |
| `entry_threshold` | `1.0` σ | Enter when curvature is at ≥1σ extreme |
| `exit_threshold` | `0.25` σ | Exit when z returns inside ±0.25σ |
| `short_duration` | `1.95` | 2Y wing duration |
| `belly_duration` | `4.5` | 5Y belly duration |
| `long_duration` | `8.0` | 10Y wing duration |

## Documentation

* [Citation](paper.md) — Litterman/Scheinkman (1991) PC3 derivation
  with explicit "why a single paper" rationale (the mean-reversion
  thesis is fully specified by the PCA decomposition; no separate
  expected-return paper is required).
* [Known failure modes](known_failures.md) — QE-driven persistent
  curvature regimes, IEF-belly duration mismatch, imperfect DV01,
  cluster overlap with `yield_curve_pca_trade`, low-Sharpe in calm
  regimes.
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed benchmark deferred to Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-rates/alphakit/strategies/rates/curve_butterfly_2s5s10s/tests
```
