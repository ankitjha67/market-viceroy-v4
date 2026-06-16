# min_variance_gtaa — Long-Only Minimum-Variance Portfolio on Stocks / Bonds / Commodities

CST (2006) minimum-variance construction on AFP (2012) / HB (1991)'s
canonical 3-asset risk-parity universe: stocks (SPY), long bonds
(TLT), broad commodities (DBC). Same universe as
`risk_parity_erc_3asset` and `max_diversification` — only the
solver objective differs.

This is the **second strategy** in the Session 2G covariance-
primitive group (Commits 5-7). Inherits the established
`_covariance` helper integration pattern from Commit 5; the only
delta is `solve_min_variance_weights` instead of `solve_erc_weights`.

> Rolling 252-day covariance with Ledoit-Wolf 2004 shrinkage.
> Solve long-only minimum-variance weights via SciPy SLSQP
> (`_covariance.solve_min_variance_weights`). Monthly rebalance.

## Quickstart

```python
from alphakit.strategies.macro import MinVarianceGtaa
from alphakit.bridges import vectorbt_bridge
import pandas as pd

prices: pd.DataFrame = ...  # ["SPY", "TLT", "DBC"]

strategy = MinVarianceGtaa()
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
| `stocks_symbol` | `"SPY"` | US large-cap equity ETF |
| `bonds_symbol` | `"TLT"` | 20+ year Treasury ETF |
| `commodities_symbol` | `"DBC"` | Broad-commodity ETF |
| `cov_window_days` | `252` | Rolling window for covariance estimation |
| `shrinkage` | `"ledoit_wolf"` | LW 2004 / `"constant"` / `"none"` |
| `max_weight` | `1.0` | Per-asset upper bound on long-only weight |

See [`config.yaml`](config.yaml) for the full default configuration
and [`strategy.py`](strategy.py) for the implementation docstring.

## Documentation

* [Foundational + primary citations](paper.md) — CST (2006)
  long-only MV theory + HB (1991) low-vol empirical anomaly
* [Known failure modes](known_failures.md) — long-only constraint
  binding, lowest-vol-asset concentration, cluster overlap with
  Session 2G covariance group siblings
* [Benchmark](benchmark_results.json) — fixture-derived metrics.
  Real-feed yfinance benchmark deferred to Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-macro/alphakit/strategies/macro/min_variance_gtaa/tests
```
