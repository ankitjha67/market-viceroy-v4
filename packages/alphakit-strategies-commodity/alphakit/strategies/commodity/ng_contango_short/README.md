# ng_contango_short — Natural-Gas Contango Short

Single-asset short-only carry on natural gas. Short the front-month
contract when the smoothed front-vs-next roll yield is negative
(contango); flat otherwise. Asymmetric mirror of
`wti_backwardation_carry`.

> Compute roll yield = (F1 − F2) / F2 daily. Smooth over 21 days.
> Short when smoothed < 0; cash otherwise. Per Bessembinder 1992
> hedging-pressure premium / Erb-Harvey 2006 §III applied to the
> canonical-most-contangoed commodity (natural gas).

## Quickstart

```python
from alphakit.strategies.commodity import NGContangoShort
from alphakit.bridges import vectorbt_bridge
import pandas as pd

prices: pd.DataFrame = ...  # ["NG=F", "NG2=F"]

strategy = NGContangoShort()
result = vectorbt_bridge.run(
    strategy=strategy,
    prices=prices,
    initial_cash=100_000,
    commission_bps=5,
)

print(f"Sharpe: {result.sharpe:.2f}")
print(f"Max DD: {result.max_dd:.1%}")
```

The strategy *consumes* both columns to compute the curve slope
but only *trades* the front-month leg. The output DataFrame has a
single column keyed on `front_symbol` (default `"NG=F"`).

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `front_symbol` | `"NG=F"` | Front-month NG column |
| `next_symbol` | `"NG2=F"` | Next-listed-month NG column |
| `smoothing_days` | `21` | Rolling-mean window for the roll yield |
| `contango_threshold` | `0.0` | Min |smoothed roll yield| for short |

See [`config.yaml`](config.yaml) for the full default configuration
and [`strategy.py`](strategy.py) for the implementation docstring.

## Documentation

* [Foundational + primary citations](paper.md) — Bessembinder 1992
  hedging-pressure premium / Erb-Harvey 2006 §III applied to NG
* [Known failure modes](known_failures.md) — polar-vortex spikes
  (2014, 2018, 2021), winter-backwardation cash periods,
  curve-flip lag, **storage-glut short-squeeze risk**, F2 proxy
  bias near roll boundaries
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed yfinance-futures benchmark deferred to
  Session 2H.

## When to use this

`ng_contango_short` is the right choice when you want to **harvest
the producer-hedging premium** that long-only NG investors pay.
It pairs naturally with `wti_backwardation_carry` (long-only crude
carry) — together the two strategies form a long-backwardation /
short-contango book on the two most curve-distinct commodities
in the panel. The cross-sectional alternative is
`commodity_curve_carry` (Commit 6), which trades both legs across
the full 8-commodity panel.

## Tests

```bash
uv run pytest packages/alphakit-strategies-commodity/alphakit/strategies/commodity/ng_contango_short/tests
```
