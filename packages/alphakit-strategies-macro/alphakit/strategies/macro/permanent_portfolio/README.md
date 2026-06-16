# permanent_portfolio — Browne 1987 / Estrada 2018 Permanent Portfolio

Static 25/25/25/25 allocation across equity (SPY), long bonds (TLT),
gold (GLD), and cash / short Treasuries (SHY). The simplest allocator
in the Session 2G macro family — its role is to establish the family
pattern (multi-asset target weights, monthly rebalance,
vectorbt-bridge integration) before the architecturally novel
strategies (covariance-based, regime-state) layer on top.

> Equal-weight the four asset classes that respond differently to
> the four major economic regimes — prosperity (equity), deflation
> (long bonds), inflation (gold), tight money / recession (cash) —
> and rebalance back to 25/25/25/25 monthly.

## Quickstart

```python
from alphakit.strategies.macro import PermanentPortfolio
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# Multi-column panel of daily closing prices for the four legs.
prices: pd.DataFrame = ...  # ["SPY", "TLT", "GLD", "SHY"]

strategy = PermanentPortfolio()
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
| `equity_symbol` | `"SPY"` | US large-cap equity ETF |
| `bonds_symbol`  | `"TLT"` | 20+ year Treasury ETF |
| `gold_symbol`   | `"GLD"` | Physical gold ETF |
| `cash_symbol`   | `"SHY"` | 1-3 year Treasury ETF (cash proxy) |
| `target_weights` | `(0.25, 0.25, 0.25, 0.25)` | Per-leg targets, must sum to 1.0 |

See [`config.yaml`](config.yaml) for the full default configuration
and [`strategy.py`](strategy.py) for the implementation docstring.

## Documentation

* [Foundational + primary citations](paper.md) — Browne (1987) and
  Estrada (2018) SSRN 3168697
* [Known failure modes](known_failures.md) — strong bull markets,
  high-inflation regimes when gold lags, real-rate spikes,
  rebalance-frequency drift, cluster expectations
* [Benchmark](benchmark_results.json) — fixture-derived Sharpe /
  drawdown. Real-feed yfinance benchmark deferred to Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-macro/alphakit/strategies/macro/permanent_portfolio/tests
```
