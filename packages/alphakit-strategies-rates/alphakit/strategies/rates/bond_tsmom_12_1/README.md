# bond_tsmom_12_1 — 12/1 Time-Series Momentum on Bonds

Single-asset adaptation of Asness/Moskowitz/Pedersen (2013) §V to a
10-year US Treasury bond proxy.

> Compute the trailing 12-month bond return excluding the most recent
> month. Go long if positive, short if negative, hold one month,
> rebalance.

## Quickstart

```python
from alphakit.strategies.rates import BondTSMOM12m1m
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# Load a bond price panel (TLT total-return-adjusted close, or a
# duration-approximated price derived from FRED DGS10).
prices: pd.DataFrame = ...

strategy = BondTSMOM12m1m()
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
| `lookback_months` | `12` | Total months of history sampled |
| `skip_months` | `1` | Most-recent months skipped (12/1 convention) |
| `threshold` | `0.0` | Absolute return below which signal is flat |

See [`config.yaml`](config.yaml) for the full default configuration
and [`strategy.py`](strategy.py) for the implementation docstring.

## Documentation

* [Foundational + primary citations](paper.md) — Moskowitz/Ooi/Pedersen
  (2012) and Asness/Moskowitz/Pedersen (2013) §V
* [Known failure modes](known_failures.md) — 2022 rate shock, range-bound
  whipsaw, single-asset under-performance vs diversified book,
  duration-approximation bias, cluster correlation with sibling rates
  strategies
* [Synthetic benchmark](benchmark_results.json) — fixture-based
  Sharpe / Sortino / Calmar / max-drawdown reference. Real-feed
  benchmark deferred to Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-rates/alphakit/strategies/rates/bond_tsmom_12_1/tests
```
