# duration_targeted_momentum — Duration-Adjusted Cross-Sectional Bond Momentum

Cross-sectional 12/1 momentum on US Treasury bond ETFs, with each
bond's trailing return divided by its modified duration before
ranking. Per Durham (2015) §III–IV, duration adjustment increases
the Sharpe of the bond cross-sectional momentum signal by ~50% over
the un-adjusted version, by isolating the per-unit-of-risk return
from the duration exposure.

> Long the top-ranked duration-adjusted-momentum bond, short the
> bottom; rebalance monthly. Dollar-neutral (weights sum to zero).

## Quickstart

```python
from alphakit.strategies.rates import DurationTargetedMomentum
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# N-column panel of bond ETF prices.
prices: pd.DataFrame = ...   # e.g. ["SHY", "IEF", "TLT"]

strategy = DurationTargetedMomentum()
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
| `lookback_months` | `12` | 12/1 trailing window |
| `skip_months` | `1` | skip most-recent month |
| `durations` | `{SHY: 1.95, IEF: 8.0, TLT: 17.0}` | per-bond modified duration |

## Documentation

* [Citation](paper.md) — Durham (2015) Federal Reserve Board WP.
  Duration adjustment isolates the per-unit-of-risk momentum
  signal from raw duration exposure.
* [Known failure modes](known_failures.md) — regime transitions,
  coarse N=3 ranking, ETF basket duration drift, cluster overlap
  with `bond_tsmom_12_1`.
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed benchmark deferred to Session 2H, with
  a wider 5+ FRED constant-maturity panel for closer match to
  Durham's specification.

## Tests

```bash
uv run pytest packages/alphakit-strategies-rates/alphakit/strategies/rates/duration_targeted_momentum/tests
```
