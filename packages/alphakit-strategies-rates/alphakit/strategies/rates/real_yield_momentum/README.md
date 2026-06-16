# real_yield_momentum — TSMOM 12/1 on TIPS Real-Yield Bond Returns

12/1 time-series momentum on TIPS real-yield-derived bond returns.
Same mechanic as `bond_tsmom_12_1` but applied to TIPS real yields
rather than nominal yields. Foundational citation: Pflueger/Viceira
(2011) — real yields are a distinct mean-reverting state variable
from nominal yields. Primary methodology: Asness §V — 12/1 momentum
generalises across asset classes including bonds.

> Trailing 12-month real-bond return excluding the most recent
> month. Long if positive, short if negative. Hold one month,
> rebalance.

## Quickstart

```python
from alphakit.strategies.rates import RealYieldMomentum
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# 1-column TIPS bond proxy panel.
prices: pd.DataFrame = ...   # e.g. ["TIP"]

strategy = RealYieldMomentum()
result = vectorbt_bridge.run(
    strategy=strategy,
    prices=prices,
    initial_cash=100_000,
    commission_bps=2,
)
```

## Parameters

Identical to `bond_tsmom_12_1`:

| Parameter | Default | Meaning |
|---|---|---|
| `lookback_months` | `12` | 12/1 trailing window |
| `skip_months` | `1` | skip most-recent month |
| `threshold` | `0.0` | filter marginal signals |

## Documentation

* [Foundational + primary citations](paper.md) — Pflueger/Viceira
  (2011) and Asness/Moskowitz/Pedersen (2013) §V; explicit
  differentiation from `bond_tsmom_12_1`.
* [Known failure modes](known_failures.md) — same as `bond_tsmom_12_1`
  plus TIPS-specific risks (liquidity squeeze, inflation-accrual
  leakage in the proxy).
* [Synthetic benchmark](benchmark_results.json) —
  fixture-based metrics. Real-feed FRED `DFII10` benchmark deferred
  to Session 2H.
