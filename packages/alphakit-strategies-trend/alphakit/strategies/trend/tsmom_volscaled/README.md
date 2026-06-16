# tsmom_volscaled — Time-Series Momentum with Continuous Signal

Reference implementation of Hurst, Ooi & Pedersen (2017),
*A Century of Evidence on Trend-Following Investing*.

> Same direction as MOP (2012) time-series momentum, but the signal is
> a continuous ``tanh`` of the lookback-return z-score instead of a
> discrete ``sign()``. The strategy runs a smaller gross book when the
> trend is weak and a full vol-targeted book when the trend is strong.

## Quickstart

```python
from alphakit.strategies.trend import TimeSeriesMomentumVolScaled
from alphakit.bridges import vectorbt_bridge
import pandas as pd

prices: pd.DataFrame = ...  # daily adjusted closes, DatetimeIndex
strategy = TimeSeriesMomentumVolScaled()
result = vectorbt_bridge.run(strategy=strategy, prices=prices, commission_bps=5)
print(f"Sharpe: {result.metrics['sharpe']:.2f}")
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `lookback_months` | `12` | total months used to build the z-score |
| `skip_months` | `1` | most-recent months skipped |
| `signal_scale` | `1.0` | tanh input scale (larger = sharper) |
| `vol_target_annual` | `0.10` | per-asset vol target |
| `vol_lookback_days` | `63` | rolling window for realised vol |
| `annualization` | `252` | trading days per year |
| `max_leverage_per_asset` | `3.0` | safety cap |

## See also

* [`paper.md`](paper.md) — full citation and abstract
* [`known_failures.md`](known_failures.md) — documented regimes where the strategy underperforms
* [`config.yaml`](config.yaml) — default configuration
* [`../tsmom_12_1`](../tsmom_12_1) — the discrete-signal (MOP 2012) baseline
