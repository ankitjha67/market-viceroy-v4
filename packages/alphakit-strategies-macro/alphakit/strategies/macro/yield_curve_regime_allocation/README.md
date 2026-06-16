# yield_curve_regime_allocation — Estrella-Hardouvelis 1991 / Ang-Piazzesi-Wei 2006 Yield-Curve Slope Regime Allocation

3-cell yield-curve-slope regime allocation. Reads two raw yield-
level informational columns (DGS10, DGS2) and computes the 2s10s
slope internally — the slope goes negative on inversion, so it
cannot itself be a bridge-passed column (the raw yield *levels*
are positive; the derived slope stays a local variable). Third
strategy in the Session 2G regime-state group.

> Each month-end, compute the lagged 10y-2y Treasury slope. If the
> curve is steep (slope ≥ 1%), hold equity-heavy 70/30; if flat,
> hold balanced 40/40/20; if inverted (slope < 0), rotate to
> defensive 60% TLT / 40% GLD.

## Quickstart

```python
from alphakit.strategies.macro import YieldCurveRegimeAllocation
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# 3 tradable ETFs + 2 informational FRED yield columns
prices: pd.DataFrame = ...  # ["SPY", "TLT", "GLD", "DGS10", "DGS2"]

strategy = YieldCurveRegimeAllocation()
result = vectorbt_bridge.run(strategy=strategy, prices=prices, commission_bps=5)
print(f"Sharpe: {result.metrics['sharpe']:.2f}")
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `equity_symbol` | `"SPY"` | Pro-cyclical equity leg |
| `bonds_symbol` | `"TLT"` | Defensive long-duration bonds |
| `gold_symbol` | `"GLD"` | Defensive inflation hedge |
| `long_yield_column` | `"DGS10"` | FRED 10-year yield |
| `short_yield_column` | `"DGS2"` | FRED 2-year yield (DGS2 over DGS3MO for ZIRP positivity) |
| `steep_threshold` | `1.0` | Slope % at/above which curve is "steep" |
| `flat_threshold` | `0.0` | Slope % boundary between flat and inverted |
| `yield_lag_months` | `1` | Publication-lag shift |
| `regime_weights` | EH/APW defaults | 3-cell allocation mapping |

See [`config.yaml`](config.yaml) and [`strategy.py`](strategy.py).

## Documentation

* [Citations](paper.md) — Estrella-Hardouvelis (1991) + Ang-
  Piazzesi-Wei (2006)
* [Known failure modes](known_failures.md) — false-positive
  inversions, DGS2-vs-DGS3MO bridge-positivity rationale, regime-
  boundary whipsaw, cluster overlap with recession_probability_rotation
* [Benchmark](benchmark_results.json) — fixture-derived metrics.
  Real-feed FRED benchmark deferred to Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-macro/alphakit/strategies/macro/yield_curve_regime_allocation/tests
```
