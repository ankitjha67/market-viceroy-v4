# crush_spread — Soybean Crush Spread Mean Reversion

3-leg mean-reversion trade on the soybean processing margin. Long
the crush (long meal + oil, short soybeans) when the rolling
z-score is below -2σ; short the crush when z > +2σ; flat when
|z| < 0.5σ.

> Compute crush = 1.5 × ZM + 0.8 × ZL − 1 × ZS daily. Rolling
> z-score over 252 days. Long when z < -2; short when z > +2.
> Per Simon 1999 risk-arbitrage framework on the 1:1.5:0.8
> bushel-equivalent ratio (Working 1949 storage theory).

## Quickstart

```python
from alphakit.strategies.commodity import CrushSpread
from alphakit.bridges import vectorbt_bridge
import pandas as pd

prices: pd.DataFrame = ...  # ["ZS=F", "ZM=F", "ZL=F"]

strategy = CrushSpread()
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
| `soybean_symbol` | `"ZS=F"` | Soybean leg |
| `meal_symbol` | `"ZM=F"` | Soybean meal leg |
| `oil_symbol` | `"ZL=F"` | Soybean oil leg |
| `zscore_lookback_days` | `252` | Rolling z-score window |
| `entry_threshold` | `2.0` | |z| to enter |
| `exit_threshold` | `0.5` | |z| to exit (hysteresis) |

The 1:1.5:0.8 ratio is hardcoded: per-leg weights 0.303 / 0.455 /
0.242 (sum |w| = 1) preserving the canonical bushel-equivalent
ratio.

## Documentation

* [Foundational + primary citations](paper.md) — Working (1949)
  storage theory + Simon (1999) crush-spread mean-reversion
  empirical evidence
* [Known failure modes](known_failures.md) — biofuel-mandate
  regime shifts, **2018 China-tariff shock (largest historical
  failure)**, drought / weather shocks (2012), bushel-equivalent
  simplification bias, multi-leg execution risk
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed yfinance-futures benchmark deferred to
  Session 2H.

## When to use this

`crush_spread` is the right choice when you want to **harvest the
soybean-processor mean-reversion premium** — a niche
risk-arbitrage trade that is largely uncorrelated with trend,
momentum, and curve-carry signals. Pairs naturally with
`crack_spread` (independent processing-margin trade in the
petroleum complex).

## Tests

```bash
uv run pytest packages/alphakit-strategies-commodity/alphakit/strategies/commodity/crush_spread/tests
```
