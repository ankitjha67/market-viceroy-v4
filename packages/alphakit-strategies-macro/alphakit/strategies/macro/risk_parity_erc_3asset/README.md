# risk_parity_erc_3asset — Equal-Risk-Contribution Portfolio on Stocks / Bonds / Commodities

MRT (2010) ERC construction on AFP (2012)'s canonical 3-asset
risk-parity universe: stocks (SPY), long bonds (TLT), broad
commodities (DBC). Each asset's marginal risk contribution
``RC_i = w_i · (Σw)_i / sqrt(wᵀΣw)`` is equal across the three
assets at the ERC optimum.

This is the **first strategy** in the Session 2G covariance-
primitive group (Commits 5-7) and the first consumer of the
shared `_covariance` helper module
(`alphakit.strategies.macro._covariance`).

> Rolling 252-day covariance with Ledoit-Wolf 2004 shrinkage to a
> constant-correlation target. Solve ERC weights via the convex
> Spinu (2013) reformulation (L-BFGS-B with log-barrier objective
> through the `_covariance` helper). Monthly rebalance.

## Quickstart

```python
from alphakit.strategies.macro import RiskParityErc3Asset
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# Multi-column panel of daily closing prices for the 3 legs.
prices: pd.DataFrame = ...  # ["SPY", "TLT", "DBC"]

strategy = RiskParityErc3Asset()
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
| `stocks_symbol` | `"SPY"` | US large-cap equity ETF |
| `bonds_symbol`  | `"TLT"` | 20+ year Treasury ETF (long duration) |
| `commodities_symbol` | `"DBC"` | Broad-commodity ETF |
| `cov_window_days` | `252` | Rolling window for covariance estimation |
| `shrinkage` | `"ledoit_wolf"` | LW 2004 / `"constant"` / `"none"` |

See [`config.yaml`](config.yaml) for the full default configuration
and [`strategy.py`](strategy.py) for the implementation docstring.

## Documentation

* [Foundational + primary citations](paper.md) — MRT (2010) ERC
  construction + AFP (2012) risk-premium justification
* [Known failure modes](known_failures.md) — covariance-estimation
  failures, single-asset-vol-spikes overweighting low-vol bonds,
  cluster overlap with permanent_portfolio (ρ ≈ 0.60-0.75)
* [Benchmark](benchmark_results.json) — fixture-derived metrics.
  Real-feed yfinance benchmark deferred to Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-macro/alphakit/strategies/macro/risk_parity_erc_3asset/tests
```
