# wti_backwardation_carry — WTI Crude-Oil Backwardation Carry

Single-asset long-only carry on WTI crude oil. Long the front-month
contract when the smoothed front-vs-next roll yield is positive
(backwardation); flat otherwise.

> Compute roll yield = (F1 − F2) / F2 daily. Smooth over 21 days.
> Long when smoothed > 0; cash otherwise. Per Erb/Harvey 2006 §III
> applied to the canonical-most-backwardated commodity (crude oil).

## Quickstart

```python
from alphakit.strategies.commodity import WTIBackwardationCarry
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# Two-column DataFrame: front + next-month WTI continuous contracts.
prices: pd.DataFrame = ...  # ["CL=F", "CL2=F"]

strategy = WTIBackwardationCarry()
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
single column keyed on `front_symbol` (default `"CL=F"`).

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `front_symbol` | `"CL=F"` | Front-month WTI column |
| `next_symbol` | `"CL2=F"` | Next-listed-month WTI column |
| `smoothing_days` | `21` | Rolling-mean window for the roll yield |
| `backwardation_threshold` | `0.0` | Min smoothed roll yield for long |

See [`config.yaml`](config.yaml) for the full default configuration
and [`strategy.py`](strategy.py) for the implementation docstring.

## Documentation

* [Foundational + primary citations](paper.md) — Gorton/Rouwenhorst
  (2006) and Erb/Harvey (2006) §III applied to WTI specifically
* [Known failure modes](known_failures.md) — persistent-contango
  regimes (2014-15 oil glut, 2020 H1 COVID), curve-flip lag at
  regime boundaries, F2 proxy bias near roll boundaries, **negative
  front-month price (April 2020)** rejected by input validation
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed yfinance-futures benchmark deferred to
  Session 2H.

## When to use this

`wti_backwardation_carry` is the right choice when you want a
**clean, crude-specific carry sleeve** — for example, an inflation-
hedge book that separates oil carry from grain carry, or a tactical
overlay on a long-only commodity allocation. By construction it is
in cash whenever crude is contangoed, so it pairs naturally with
`ng_contango_short` (contango-side trade) and
`commodity_curve_carry` (cross-sectional rank book).

## Tests

```bash
uv run pytest packages/alphakit-strategies-commodity/alphakit/strategies/commodity/wti_backwardation_carry/tests
```
