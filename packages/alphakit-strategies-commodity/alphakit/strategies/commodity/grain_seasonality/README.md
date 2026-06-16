# grain_seasonality — US Grain Futures Calendar Seasonality

Calendar-based seasonal trade on US grain futures (corn, soybeans,
wheat). Long during the planting-uncertainty months and short
during the post-harvest months per Sørensen (2002) §III.

> Per grain, hardcode the Sørensen seasonal calendar:
> - ZC=F long Apr-Jun, short Sep-Nov
> - ZS=F long May-Jul, short Oct-Dec
> - ZW=F long Feb-Apr, short Jul-Aug
>
> Output ±1 per leg per the calendar; flat in non-window months.

## Quickstart

```python
from alphakit.strategies.commodity import GrainSeasonality
from alphakit.bridges import vectorbt_bridge
import pandas as pd

prices: pd.DataFrame = ...  # ["ZC=F", "ZS=F", "ZW=F"]

strategy = GrainSeasonality()
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
| `universe` | `("ZC=F", "ZS=F", "ZW=F")` | Grains to trade |

The seasonal calendar is hardcoded inside the strategy module per
Sørensen (2002) §III; only symbols with a calendar entry are
allowed in the universe. See [`config.yaml`](config.yaml) for the
full default configuration and [`strategy.py`](strategy.py) for
the calendar.

## Documentation

* [Foundational + primary citations](paper.md) — Fama/French
  (1987) storage theory + Sørensen (2002) seasonality calendar
* [Known failure modes](known_failures.md) — bumper-crop years
  (2014, 2017), weather-disruption years (2012 drought, 2020
  China-panic, 2022 Ukraine), **non-US grain dynamics post-2010**,
  climate-change calendar drift
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed yfinance-futures benchmark deferred to
  Session 2H.

## When to use this

`grain_seasonality` is the right choice when you want to **harvest
the agricultural-storage premium** — it is largely orthogonal to
trend, momentum, and curve-carry signals because the calendar is
set by the agricultural year, not the macro cycle. Pairs naturally
with `commodity_curve_carry` (curve carry on the same grains
panel) and `commodity_tsmom` for a multi-signal grains book.

## Tests

```bash
uv run pytest packages/alphakit-strategies-commodity/alphakit/strategies/commodity/grain_seasonality/tests
```
