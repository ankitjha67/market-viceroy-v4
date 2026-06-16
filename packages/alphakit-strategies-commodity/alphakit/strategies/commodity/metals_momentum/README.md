# metals_momentum — Metals-Only 12/1 Time-Series Momentum

Metals-focused adaptation of Asness/Moskowitz/Pedersen (2013) §V to
a 4-metal continuous-contract futures panel (gold, silver, copper,
platinum).

> Per metal, compute the trailing 12-month return excluding the
> most recent month. Long if positive, short if negative. Vol-scale
> to a 10% per-asset target. Hold one month, rebalance.

## Quickstart

```python
from alphakit.strategies.commodity import MetalsMomentum
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# Multi-column panel of metals continuous-contract closing prices.
prices: pd.DataFrame = ...  # ["GC=F", "SI=F", "HG=F", "PL=F"]

strategy = MetalsMomentum()
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
  (2012) and Asness/Moskowitz/Pedersen (2013) §V applied to the
  metals subset
* [Known failure modes](known_failures.md) — range-bound metals
  (gold 2013-18, copper 2014-16), sharp metals reversals (2008,
  2013, 2020 silver squeeze), industrial-vs-monetary divergence,
  continuous-contract roll bias, **strong cluster overlap with
  `commodity_tsmom`** (ρ ≈ 0.75-0.90)
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed yfinance-futures benchmark deferred to
  Session 2H.

## When to prefer this over `commodity_tsmom`

`metals_momentum` is the right choice when you want **metals beta
without energy or grain exposure** — for example, an inflation-hedge
sleeve, an industrial-cycle expression, or a complementary
allocation alongside an energy- or agriculture-focused book.
`commodity_tsmom` is the right choice when you want broad commodity
TSMOM with built-in cross-sector diversification.

The two strategies share the same mechanic and have a strong
cluster correlation (ρ ≈ 0.75-0.90); both ship because the choice
of universe is itself the point. See `known_failures.md` §6 for
the cluster-risk acceptance.

## Tests

```bash
uv run pytest packages/alphakit-strategies-commodity/alphakit/strategies/commodity/metals_momentum/tests
```
