# commodity_curve_carry — Cross-Sectional Commodity Curve Carry

Cross-sectional curve-carry on an 8-commodity panel. Long the top
tercile by roll yield (most-backwardated), short the bottom tercile
(most-contangoed), equal-weighted within each leg, dollar-neutral
by construction.

> Per commodity, compute roll yield = (F1 − F2) / F2 daily.
> Smooth over 21 days. Rank cross-sectionally each month-end. Long
> top 1/3, short bottom 1/3, equal weight per leg. Per Koijen-
> Moskowitz-Pedersen-Vrugt 2018 §IV unified-carry framework.

## Quickstart

```python
from alphakit.strategies.commodity import CommodityCurveCarry
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# Multi-column panel: 8 fronts + 8 next-month proxies.
prices: pd.DataFrame = ...  # ["CL=F", "CL2=F", "NG=F", "NG2=F", ...]

strategy = CommodityCurveCarry()
result = vectorbt_bridge.run(
    strategy=strategy,
    prices=prices,
    initial_cash=100_000,
    commission_bps=5,
)

print(f"Sharpe: {result.sharpe:.2f}")
print(f"Max DD: {result.max_dd:.1%}")
```

The strategy *consumes* both front and next columns and *trades*
only the front-month leg (output columns are the keys of
`front_next_map`).

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `front_next_map` | 8-commodity map | `{front: next}` pairing |
| `top_quantile` | `1/3` | Long the top fraction of the rank |
| `bottom_quantile` | `1/3` | Short the bottom fraction |
| `smoothing_days` | `21` | Rolling-mean window for the roll yield |
| `min_panel_size` | `4` | Min commodities to form a rank |

See [`config.yaml`](config.yaml) for the full default configuration
and [`strategy.py`](strategy.py) for the implementation docstring.

## Documentation

* [Foundational + primary citations](paper.md) — Erb/Harvey (2006)
  §III foundational + Koijen/Moskowitz/Pedersen/Vrugt (2018) §IV
  primary
* [Known failure modes](known_failures.md) — flat-curve regimes
  (2014-15 glut, 2020 H1 COVID), sharp curve flips, single-leg
  blow-ups, **smaller-universe penalty vs KMPV §IV's 24-commodity
  panel** (8-commodity AlphaKit default → ~30-40% lower long-run
  Sharpe)
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed yfinance-futures benchmark deferred to
  Session 2H.

## When to use this

`commodity_curve_carry` is the right choice when you want the
**diversified cross-sectional carry premium** — pairs both legs
of the curve across a multi-commodity panel, captures the
dispersion-driven Sharpe lift, and is dollar-neutral by
construction. Pairs naturally with `commodity_tsmom` (cross-
sectional momentum on the same panel) for a multi-signal
commodity book.

For a clean single-asset expression, use the EH06 §III siblings:
`wti_backwardation_carry` (long-only WTI) or `ng_contango_short`
(short-only NG).

## Tests

```bash
uv run pytest packages/alphakit-strategies-commodity/alphakit/strategies/commodity/commodity_curve_carry/tests
```
