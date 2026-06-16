# credit_spread_momentum — IG Credit Bond Momentum (6/0)

Single-asset 6-month momentum on investment-grade corporate bond
returns. Per Jostova et al. (2013) §III: trailing 6-month return on
corporate bonds predicts the next 6 months. Sign-of-return signal,
no skip month (unlike Treasuries).

> Long IG when trailing 6-month return is positive, short when
> negative. Hold one month, rebalance.

## Quickstart

```python
from alphakit.strategies.rates import CreditSpreadMomentum
from alphakit.bridges import vectorbt_bridge
import pandas as pd

prices: pd.DataFrame = ...   # ["LQD"] or another IG bond ETF

strategy = CreditSpreadMomentum()
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
| `lookback_months` | `6` | trailing window |
| `skip_months` | `0` | no skip on corporates |
| `threshold` | `0.0` | filter marginal signals |

## Documentation

* [Citation](paper.md) — Jostova et al. (2013); explicit
  differentiation from sibling momentum strategies and from the
  Phase 1 carry-family `bond_carry_roll`.
* [Known failure modes](known_failures.md) — credit-cycle
  inflection lag, IG-vs-HY decoupling, asset-specific
  microstructure shocks, cluster overlap with sovereign-bond
  momentum.
* [Synthetic benchmark](benchmark_results.json) —
  fixture-based metrics. Real-feed FRED `BAMLC0A0CM` (IG OAS) +
  LQD benchmark deferred to Session 2H.
