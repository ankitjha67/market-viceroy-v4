# vigilant_asset_allocation_5 — Keller-Keuning 2017 VAA-G4 (5-ETF variant)

VAA-G4 with the defensive bucket collapsed to a single SHY leg.
Combines a weighted 13612W momentum aggregator (1/3/6/12-month
returns) with a canary-asset breadth-momentum gate that switches
the portfolio to cash when any offensive asset's score turns
non-positive.

> Each month-end, compute the 13612W score for each of the 4
> offensive ETFs (SPY/EFA/EEM/AGG) and the defensive cash bucket
> (SHY). If *any* offensive score is non-positive, hold 100% SHY.
> Otherwise hold 100% of the highest-scoring offensive ETF.

## Quickstart

```python
from alphakit.strategies.macro import VigilantAssetAllocation5
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# Multi-column panel of daily closing prices for the 5 ETFs.
prices: pd.DataFrame = ...  # ["SPY", "EFA", "EEM", "AGG", "SHY"]

strategy = VigilantAssetAllocation5()
result = vectorbt_bridge.run(
    strategy=strategy,
    prices=prices,
    initial_cash=100_000,
    commission_bps=5,
)

print(f"Sharpe: {result.metrics['sharpe']:.2f}")
print(f"Max DD: {result.metrics['max_drawdown']:.1%}")
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `offensive_symbols` | `("SPY", "EFA", "EEM", "AGG")` | 4 offensive / canary ETFs |
| `defensive_symbol` | `"SHY"` | Cash-bucket fallback ETF |
| `score_weights` | `(12.0, 4.0, 2.0, 1.0)` | 13612W aggregator weights |
| `lookbacks_months` | `(1, 3, 6, 12)` | Lookback windows for the 4 return components |

See [`config.yaml`](config.yaml) for the full default configuration
and [`strategy.py`](strategy.py) for the implementation docstring.

## Documentation

* [Foundational + primary citations](paper.md) — Keller-Keuning
  (2014) generalized momentum + (2017) breadth-momentum canary gate
* [Known failure modes](known_failures.md) — whipsaw in indecisive
  markets, single-asset concentration risk, cluster overlap with
  Phase 1 `dual_momentum_gem` (ρ ≈ 0.40-0.60)
* [Benchmark](benchmark_results.json) — fixture-derived metrics.
  Real-feed yfinance benchmark deferred to Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-macro/alphakit/strategies/macro/vigilant_asset_allocation_5/tests
```
