# recession_probability_rotation — Estrella-Mishkin 1998 / Wright 2006 Recession-Probability Asset Rotation

Threshold-based asset rotation driven by the Cleveland Fed
recession probability (FRED `RECPROUSM156N`). First strategy in
the Session 2G regime-state group (Commits 8-12) and the first
consumer of the **informational-column pattern** per Session 2D
`docs/phase-2-amendments.md` §2D sub-section 3 — FRED series
enters as a zero-weight input column alongside the tradable
ETFs.

> Each month-end, read the lagged Cleveland Fed recession
> probability (1-month publication lag). If probability is below
> 30% threshold, hold pro-cyclical 60/40 (SPY/TLT). If at or
> above the threshold, rotate to defensive (TLT/GLD).

## Quickstart

```python
from alphakit.strategies.macro import RecessionProbabilityRotation
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# Input includes 3 tradable ETFs + 1 informational FRED column
prices: pd.DataFrame = ...  # ["SPY", "TLT", "GLD", "RECPROUSM156N"]

strategy = RecessionProbabilityRotation()
result = vectorbt_bridge.run(
    strategy=strategy,
    prices=prices,
    initial_cash=100_000,
    commission_bps=5,
)
print(f"Sharpe: {result.metrics['sharpe']:.2f}")
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `equity_symbol` | `"SPY"` | Pro-cyclical equity leg |
| `bonds_symbol` | `"TLT"` | Defensive long-duration bonds |
| `gold_symbol` | `"GLD"` | Defensive inflation hedge |
| `recession_column` | `"RECPROUSM156N"` | FRED informational column |
| `recession_threshold` | `0.30` | Estrella-Mishkin canonical threshold |
| `lag_months` | `1` | FRED publication-lag shift |
| `risk_on_weights` | `(0.60, 0.40, 0.00)` | Pro-cyclical allocation |
| `risk_off_weights` | `(0.00, 0.60, 0.40)` | Defensive allocation |

See [`config.yaml`](config.yaml) for the full default configuration
and [`strategy.py`](strategy.py) for the implementation docstring.

## Documentation

* [Foundational + primary citations](paper.md) — Estrella-Mishkin
  (1998) foundational model + Wright (2006) Cleveland Fed
  production specification
* [Known failure modes](known_failures.md) — publication-lag
  forensics, model-version drift, false-positive regime calls,
  cluster overlap with yield_curve_regime_allocation
* [Benchmark](benchmark_results.json) — fixture-derived metrics.
  Real-feed FRED benchmark deferred to Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-macro/alphakit/strategies/macro/recession_probability_rotation/tests
```
