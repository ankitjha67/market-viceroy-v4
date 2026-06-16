# swap_spread_mean_rev — Swap-Treasury Basis Mean-Reversion

Mean-reversion on the swap-Treasury basis via z-score on the log-
price spread. Per Liu/Longstaff/Mandell (2006) the basis is a
stationary, mean-reverting process; per Duarte/Longstaff/Yu (2007)
trading the deviation has positive expected return net of costs but
material tail risk during funding stress.

> Long Treasury / short swap when basis is unusually wide; short
> Treasury / long swap when unusually tight. Daily rebalance,
> z-score on 252-day window.

The DLY 2007 paper title — "nickels in front of a steamroller" —
is the canonical risk warning: small profits most of the time,
large losses in stress (LTCM 1998, GFC 2008-09).

## Quickstart

```python
from alphakit.strategies.rates import SwapSpreadMeanRev
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# 2-column panel: Treasury proxy, swap-rate proxy.
prices: pd.DataFrame = ...   # ["IEF", "IRS_10Y_proxy"]

strategy = SwapSpreadMeanRev()
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
| `zscore_window` | `252` | trailing window |
| `entry_threshold` | `1.0` σ | enter on ±1σ extreme |
| `exit_threshold` | `0.25` σ | exit when |z| < 0.25σ |

## Documentation

* [Foundational + primary citations](paper.md) — Liu/Longstaff/Mandell
  (2006) and Duarte/Longstaff/Yu (2007); explicit differentiation
  from sibling slope strategies.
* [Known failure modes](known_failures.md) — funding stress
  (LTCM 1998, GFC 2008-09), negative-swap-spread regime
  (post-2010), repo/funding cost asymmetry, missing swap-rate
  data feed in Phase 2.
* [Synthetic benchmark](benchmark_results.json) —
  fixture-based metrics. Real-feed Session 2H benchmark requires
  swap-rate data adapter not yet wired up.
