# bond_carry_rolldown — Single-Asset Bond Carry-and-Rolldown Overlay

Single-asset duration positioning conditional on the slope of the US
Treasury curve. Goes long the target long bond when the slope is
elevated (z-score of the price-space slope proxy < −1.0σ), flat
otherwise.

> When the curve is steep, expected carry-and-rolldown on the long
> bond is high — KMPV (2018) §III. Hold the long bond while carry
> is elevated; flat when the curve flattens or inverts.

Foundational citation: Fama (1984) *Forward Rates as Predictors of
Future Spot Rates* — the term-premium-existence result. Primary
methodology: Koijen, Moskowitz, Pedersen & Vrugt (2018) *Carry* —
the unified carry definition operationalised across asset classes.

## Quickstart

```python
from alphakit.strategies.rates import BondCarryRolldown
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# 2-column panel: short-end (informational), target long bond.
prices: pd.DataFrame = ...   # e.g. ["SHY", "TLT"]

strategy = BondCarryRolldown()
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
| `entry_threshold` | `1.0` σ | Enter when slope proxy z-score < −1σ |
| `exit_threshold` | `0.25` σ | Exit when z-score returns above −0.25σ |

## Documentation

* [Foundational + primary citations](paper.md) — Fama (1984) and KMPV
  (2018); explicit differentiation from the steepener/flattener and
  from the carry-family `bond_carry_roll`.
* [Known failure modes](known_failures.md) — curve flattening after
  entry (2018, 2022), proxy mismatch with true yield-curve carry,
  cluster overlap with `bond_tsmom_12_1` and `g10_bond_carry`,
  single-asset concentration risk.
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed FRED benchmark deferred to Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-rates/alphakit/strategies/rates/bond_carry_rolldown/tests
```
