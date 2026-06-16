# gtaa_cross_asset_momentum — Cross-Asset GTAA 12/1 Time-Series Momentum

AMP (2013) §V applied to a cross-asset ETF panel spanning equity,
bonds, commodities, and real estate.

> For each ETF in the 9-asset universe, compute the trailing 12-month
> return excluding the most recent month. Long if positive, short if
> negative. Vol-scale each leg to a 10% per-asset target. Hold one
> month, rebalance monthly.

## Quickstart

```python
from alphakit.strategies.macro import GtaaCrossAssetMomentum
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# Multi-column panel of daily closing prices for the 9 ETFs.
prices: pd.DataFrame = ...  # ["SPY", "EFA", "EEM", "AGG", "TLT", "HYG", "GLD", "DBC", "VNQ"]

strategy = GtaaCrossAssetMomentum()
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
| `lookback_months` | `12` | Total months of history sampled |
| `skip_months` | `1` | Most-recent months skipped (12/1 convention) |
| `vol_target_annual` | `0.10` | Per-asset annual vol target |
| `vol_lookback_days` | `63` | Rolling window for realised vol |
| `annualization` | `252` | Trading days per year |
| `max_leverage_per_asset` | `3.0` | Safety cap on per-asset weight |

See [`config.yaml`](config.yaml) for the full default configuration
and [`strategy.py`](strategy.py) for the implementation docstring.

## Documentation

* [Foundational + primary citations](paper.md) — Hurst/Ooi/Pedersen
  (2017) and Asness/Moskowitz/Pedersen (2013) §V
* [Known failure modes](known_failures.md) — trendless regimes
  (2017-18), sharp regime changes (2008/2020), cross-asset
  dispersion collapse (2020 March), **cluster overlap with Phase 1
  `tsmom_12_1`** (ρ ≈ 0.65-0.85 because of shared SPY/EFA/EEM/AGG/
  GLD/DBC legs), real-estate substrate quirk
* [Benchmark](benchmark_results.json) — fixture-derived Sharpe /
  drawdown. Real-feed yfinance benchmark deferred to Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-macro/alphakit/strategies/macro/gtaa_cross_asset_momentum/tests
```
