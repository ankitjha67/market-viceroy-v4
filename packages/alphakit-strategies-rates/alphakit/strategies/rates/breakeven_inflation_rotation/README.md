# breakeven_inflation_rotation — TIPS vs Nominal Treasury Rotation

Mean-reversion rotation between TIPS (inflation-protected) and
matched-maturity nominal Treasuries, anchored on the z-score of
the breakeven inflation proxy. Long-TIPS when breakeven is
depressed (inflation expectations unsustainably low); short-TIPS
when breakeven is elevated (inflation expectations unsustainably
high).

> Z-score of log(P_TIPS) − log(P_nominal) over a rolling 1Y window.
> z > +1σ → short-TIPS rotation. z < −1σ → long-TIPS rotation.
> Hysteresis exit at ±0.25σ.

Foundational citation: Campbell & Shiller (1996) — analytical
framework for inflation-indexed government debt. Primary
methodology: Fleckenstein, Longstaff & Lustig (2014) — TIPS-
Treasury basis as a tradeable mispricing.

## Quickstart

```python
from alphakit.strategies.rates import BreakevenInflationRotation
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# 2-column panel: TIPS proxy first, nominal Treasury proxy second.
prices: pd.DataFrame = ...   # e.g. ["TIP", "IEF"]

strategy = BreakevenInflationRotation()
result = vectorbt_bridge.run(
    strategy=strategy,
    prices=prices,
    initial_cash=100_000,
    commission_bps=2,
)
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `zscore_window` | `252` | Trailing window for z-score |
| `entry_threshold` | `1.0` σ | Enter rotation on ±1σ extreme |
| `exit_threshold` | `0.25` σ | Exit when z returns inside ±0.25σ |

## Documentation

* [Foundational + primary citations](paper.md) — Campbell/Shiller
  (1996) and Fleckenstein/Longstaff/Lustig (2014); explicit deviation
  notes on the missing inflation-swap hedge and the ETF-vs-CMT
  duration mismatch.
* [Known failure modes](known_failures.md) — persistent inflation
  regime changes (2021–2022 is the canonical recent example),
  missing inflation-swap hedge residual exposure, ETF basket vs
  constant-maturity mismatch, asymmetric tail risk.
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed benchmark with `DFII10` / `DGS10`
  matched-maturity yields deferred to Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-rates/alphakit/strategies/rates/breakeven_inflation_rotation/tests
```
