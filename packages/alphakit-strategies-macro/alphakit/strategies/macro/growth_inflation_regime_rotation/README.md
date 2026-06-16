# growth_inflation_regime_rotation — Ilmanen-Maloney-Ross 2014 Growth × Inflation 4-Cell Regime Rotation

4-cell macro regime rotation driven by two FRED informational
columns (CPI index → YoY computed internally; GDP growth rate).
Second strategy in the Session 2G regime-state group; extends
Commit 8's informational-column + publication-lag pattern to
two informational columns and a 4-cell taxonomy.

> Each month-end, classify the macro regime by the cross of growth
> (GDP rate vs threshold) and inflation (CPI YoY vs threshold) —
> with both signals lagged for publication availability. Map the
> 4-cell regime to an allocation across SPY / TLT / GLD / DBC per
> IMR 2014's documented asset-class sensitivities.

## Quickstart

```python
from alphakit.strategies.macro import GrowthInflationRegimeRotation
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# 4 tradable ETFs + 2 informational FRED columns
prices: pd.DataFrame = ...  # ["SPY","TLT","GLD","DBC","CPIAUCSL","GDPC1"]

strategy = GrowthInflationRegimeRotation()
result = vectorbt_bridge.run(strategy=strategy, prices=prices, commission_bps=5)
print(f"Sharpe: {result.metrics['sharpe']:.2f}")
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `equity_symbol` | `"SPY"` | Equity leg |
| `bonds_symbol` | `"TLT"` | Long-bonds leg |
| `gold_symbol` | `"GLD"` | Gold leg |
| `commodities_symbol` | `"DBC"` | Commodities leg |
| `cpi_column` | `"CPIAUCSL"` | FRED CPI index (YoY computed internally) |
| `gdp_column` | `"GDPC1"` | FRED real GDP growth rate |
| `growth_threshold` | `2.0` | GDP rate % above which growth is "rising" |
| `inflation_threshold` | `2.5` | CPI YoY % above which inflation is "rising" |
| `cpi_lag_months` | `1` | CPI publication-lag shift |
| `gdp_lag_months` | `1` | GDP publication-lag shift (advance estimate) |
| `regime_weights` | IMR 2014 defaults | 4-cell allocation mapping |

See [`config.yaml`](config.yaml) and [`strategy.py`](strategy.py).

## Documentation

* [Citation](paper.md) — Ilmanen-Maloney-Ross (2014) sole anchor
* [Known failure modes](known_failures.md) — regime-boundary
  whipsaw, GDP quarterly-cadence lag, threshold sensitivity,
  cluster overlap with recession_probability_rotation
* [Benchmark](benchmark_results.json) — fixture-derived metrics.
  Real-feed FRED benchmark deferred to Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-macro/alphakit/strategies/macro/growth_inflation_regime_rotation/tests
```
