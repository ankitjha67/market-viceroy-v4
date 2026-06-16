# max_diversification — Maximum-Diversification Portfolio on Stocks / Bonds / Commodities

CC (2008) MDP construction with CFR (2013) extended-properties anchor
on AFP (2012)'s canonical 3-asset risk-parity universe: stocks (SPY),
long bonds (TLT), broad commodities (DBC). Same universe as
`risk_parity_erc_3asset` (Commit 5) and `min_variance_gtaa` (Commit 6)
— only the solver objective differs.

This is the **third strategy** in the Session 2G covariance-primitive
group (Commits 5-7). Inherits the established `_covariance` helper
integration pattern; consumes
`solve_max_diversification_weights` and `diversification_ratio` from
the helper.

> Rolling 252-day covariance with Ledoit-Wolf 2004 shrinkage.
> Solve long-only MDP weights via SciPy SLSQP maximising
> `DR(w) = (wᵀσ) / sqrt(wᵀΣw)`. Monthly rebalance.

## Quickstart

```python
from alphakit.strategies.macro import MaxDiversification
from alphakit.bridges import vectorbt_bridge
import pandas as pd

prices: pd.DataFrame = ...  # ["SPY", "TLT", "DBC"]

strategy = MaxDiversification()
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

* [Foundational + primary citations](paper.md) — CC (2008) MDP
  construction + CFR (2013) extended properties
* [Known failure modes](known_failures.md) — high-correlation
  regimes, estimation-error robustness vs MV, cluster overlap with
  Session 2G covariance group siblings
* [Benchmark](benchmark_results.json) — fixture-derived metrics.
  Real-feed yfinance benchmark deferred to Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-macro/alphakit/strategies/macro/max_diversification/tests
```
