# commodity_tsmom — Cross-Commodity 12/1 Time-Series Momentum

Cross-commodity adaptation of Asness/Moskowitz/Pedersen (2013) §V to
a multi-instrument continuous-contract futures panel.

> Per commodity, compute the trailing 12-month return excluding the
> most recent month. Long if positive, short if negative. Vol-scale
> to a 10% per-asset target. Hold one month, rebalance.

## Quickstart

```python
from alphakit.strategies.commodity import CommodityTSMOM12m1m
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# Multi-column panel of continuous-contract closing prices.
prices: pd.DataFrame = ...  # ["CL=F", "NG=F", "GC=F", "SI=F", "HG=F", "ZC=F", "ZS=F", "ZW=F"]

strategy = CommodityTSMOM12m1m()
result = vectorbt_bridge.run(
    strategy=strategy,
    prices=prices,
    initial_cash=100_000,
    commission_bps=5,
)

print(f"Sharpe: {result.sharpe:.2f}")
print(f"Max DD: {result.max_dd:.1%}")
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `lookback_months` | `12` | Total months of history sampled |
| `skip_months` | `1` | Most-recent months skipped (12/1 convention) |
| `vol_target_annual` | `0.10` | Per-asset annual vol target |
| `vol_lookback_days` | `63` | Rolling window for realised vol |
| `annualization` | `252` | Trading days per year |
| `max_leverage_per_asset` | `3.0` | Safety cap on per-asset weight |

See [`config.yaml`](config.yaml) for the full default configuration
and [`strategy.py`](strategy.py) for the implementation docstring.

## Documentation

* [Foundational + primary citations](paper.md) — Moskowitz/Ooi/Pedersen
  (2012) and Asness/Moskowitz/Pedersen (2013) §V
* [Known failure modes](known_failures.md) — trendless regimes (2017-18),
  sharp regime changes (2008/2014/2020), single-asset blow-ups,
  continuous-contract roll bias, **strong cluster overlap with
  `metals_momentum`** (ρ ≈ 0.75-0.90)
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed yfinance-futures benchmark deferred to
  Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-commodity/alphakit/strategies/commodity/commodity_tsmom/tests
```
