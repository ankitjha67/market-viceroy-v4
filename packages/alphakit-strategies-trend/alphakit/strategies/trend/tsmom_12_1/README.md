# tsmom_12_1 — Time-Series Momentum, 12/1

Reference implementation of Moskowitz, Ooi & Pedersen (2012).

> Go long assets with positive 12-month returns (excluding the most
> recent month), short those with negative 12-month returns, size each
> position to the same target volatility, and rebalance monthly.

## Quickstart

```python
from alphakit.strategies.trend import TimeSeriesMomentum12m1m
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# 1. Load a price panel (any source — yfinance, Stooq, Polygon, ...).
#    Index must be a pd.DatetimeIndex, columns are symbols, values are
#    adjusted close prices.
prices: pd.DataFrame = ...

# 2. Instantiate the strategy with its paper defaults.
strategy = TimeSeriesMomentum12m1m()

# 3. Backtest it.
result = vectorbt_bridge.run(
    strategy=strategy,
    prices=prices,
    initial_cash=100_000,
    commission_bps=5,
)

# 4. Inspect the metrics.
print(f"Sharpe: {result.metrics['sharpe']:.2f}")
print(f"Max DD: {result.metrics['max_drawdown']:.1%}")
```

## Parameters

See [`config.yaml`](config.yaml) for the default configuration and
[`strategy.py`](strategy.py) for the full docstring.

| Parameter | Default | Meaning |
|---|---|---|
| `lookback_months` | `12` | total months of history to sample |
| `skip_months` | `1` | most-recent months to skip |
| `vol_target_annual` | `0.10` | per-asset annual vol target |
| `vol_lookback_days` | `63` | rolling window for realised vol |
| `annualization` | `252` | trading days per year |
| `max_leverage_per_asset` | `3.0` | safety cap on per-asset weight |

## Documentation

* [Paper citation and abstract](paper.md)
* [Known failure modes](known_failures.md)
* [Out-of-sample benchmark results](benchmark_results.json)

## Tests

```bash
uv run pytest packages/alphakit-strategies-trend/alphakit/strategies/trend/tsmom_12_1/tests
```
