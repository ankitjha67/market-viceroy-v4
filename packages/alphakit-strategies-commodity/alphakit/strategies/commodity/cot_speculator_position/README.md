# cot_speculator_position — Contrarian COT Speculator-Positioning

Multi-asset contrarian trade on CFTC Commitments of Traders (COT)
non-commercial speculator positioning. Long when speculators are
extreme-short (bottom decile of 3-year history), short when
speculators are extreme-long (top decile), flat otherwise.

> Per commodity, compute net-speculator-position (long − short) /
> open interest. Compute its rolling 3-year percentile. Long when
> < 10th percentile, short when > 90th percentile. Per Bessembinder
> 1992 / de Roon-Nijman-Veld 2000 hedging-pressure framework.

> **CRITICAL**: respect the Friday-for-Tuesday COT publication lag
> (CFTC publishes Friday's report covering Tuesday's positions —
> the strategy enforces a 3-day signal shift).

## Quickstart

```python
from alphakit.strategies.commodity import COTSpeculatorPosition
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# Multi-column DataFrame: 4 prices + 4 paired positioning columns.
prices: pd.DataFrame = ...
# columns must include: ["CL=F", "NG=F", "GC=F", "ZC=F",
#                        "CL=F_NET_SPEC", "NG=F_NET_SPEC",
#                        "GC=F_NET_SPEC", "ZC=F_NET_SPEC"]

strategy = COTSpeculatorPosition()
result = vectorbt_bridge.run(
    strategy=strategy,
    prices=prices,
    initial_cash=100_000,
    commission_bps=5,
)

print(f"Sharpe: {result.sharpe:.2f}")
print(f"Max DD: {result.max_dd:.1%}")
```

The strategy *consumes* both price and positioning columns and
*trades* only the price columns. Output DataFrame has one column
per traded front symbol (the keys of `front_to_position_map`).

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `front_to_position_map` | 4-commodity map | `{front: position_column}` |
| `percentile_lookback_weeks` | `156` | Rolling window (3 years) |
| `extreme_long_threshold` | `90.0` | Pct above → short |
| `extreme_short_threshold` | `10.0` | Pct below → long |
| `cot_lag_days` | `3` | Friday-for-Tuesday lag |

See [`config.yaml`](config.yaml) for the full default configuration
and [`strategy.py`](strategy.py) for the implementation docstring.

## CFTC data ingestion

The CFTC publishes the Commitments of Traders report **every
Friday at 15:30 ET** covering positions held as of **the prior
Tuesday close**:

> [https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm)

Users running real-data backtests must:

1. Pull the weekly Combined COT report.
2. Compute the **non-commercial long fraction of open interest**:
   `NC_long / open_interest` (range `(0, 1]`). This convention
   keeps positioning columns strictly positive so the vectorbt
   bridge can validate them; the percentile-rank trading rule is
   invariant to monotonic transformations of the input.
3. Forward-fill the weekly value to a daily index aligned to the
   trading calendar.
4. Pass the daily series in as the positioning column for each
   traded commodity.

Users with raw net positioning (range `[-1, +1]`) should shift to
`(net + 1) / 2` before passing in.

The strategy applies a 3-day signal shift internally to enforce
the publication lag — do **not** double-apply by pre-lagging the
ingested data.

## Documentation

* [Foundational + primary citations](paper.md) — Bessembinder
  (1992) hedging-pressure framework + de Roon/Nijman/Veld (2000)
  contrarian-positioning result on the COT panel
* [Known failure modes](known_failures.md) — persistent-extreme
  regimes (2007-08 crude bubble, 2010-11 gold rally), CFTC data
  re-classifications (2009 Disaggregated, 2020 Special Call),
  **mis-applied Friday-for-Tuesday lag (most common failure
  mode)**, CFTC publication outages
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed CFTC + yfinance benchmark deferred to
  Session 2H.

## When to use this

`cot_speculator_position` is the right choice when you want a
**positioning-based contrarian signal** that is largely
uncorrelated with curve-carry and trend strategies. It pairs
naturally with:

* `commodity_curve_carry` (different signal dimension; ρ ≈ 0.0-0.2)
* `commodity_tsmom` (mildly negatively correlated; ρ ≈ -0.2 to 0.0)

Together the three strategies form a multi-signal commodity book
that captures three distinct premia: curve, momentum, and
positioning extremes.

## Tests

```bash
uv run pytest packages/alphakit-strategies-commodity/alphakit/strategies/commodity/cot_speculator_position/tests
```
