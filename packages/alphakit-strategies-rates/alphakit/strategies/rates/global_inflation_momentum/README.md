# global_inflation_momentum — Cross-Country Inflation Momentum Bond Tilt

Cross-sectional dollar-neutral bond tilt driven by country-level
inflation momentum. Per Ilmanen/Maloney/Ross (2014): rising
inflation predicts negative bond returns; cross-sectional rank of
inflation momentum produces a tradeable bond-tilt signal.

> Long the bond of the country with the lowest 12-month inflation
> momentum, short the bond of the country with the highest.
> Rebalance monthly. Dollar-neutral.

## Quickstart

```python
from alphakit.strategies.rates import GlobalInflationMomentum
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# Multi-column panel: paired CPI_<country> + BOND_<country> series.
prices: pd.DataFrame = ...   # ["CPI_US", "CPI_DE", "BOND_US", "BOND_DE"]

strategy = GlobalInflationMomentum()
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
| `cpi_lookback_months` | `12` | inflation momentum horizon |

## Column-naming convention

The strategy validates that every input column starts with either
``CPI_`` or ``BOND_``, and that every CPI prefix has a matching
BOND counterpart with the same country suffix:

* `CPI_US` ↔ `BOND_US`
* `CPI_DE` ↔ `BOND_DE`

Mismatched columns or non-conforming names raise ``ValueError``.

## Documentation

* [Foundational + primary citations](paper.md) — Ilmanen (2011)
  textbook and Ilmanen/Maloney/Ross (2014) JPM article. Explicit
  differentiation from `breakeven_inflation_rotation`,
  `real_yield_momentum`, and `g10_bond_carry`.
* [Known failure modes](known_failures.md) — inflation regime
  change at signal-window scale (2021-22 is canonical),
  synchronised inflation surprises, CPI release timing
  look-ahead, country panel size dependence.
* [Synthetic benchmark](benchmark_results.json) —
  fixture-based metrics. Real-feed Session 2H benchmark with
  paired G7 CPI + bond series required for meaningful evaluation.
