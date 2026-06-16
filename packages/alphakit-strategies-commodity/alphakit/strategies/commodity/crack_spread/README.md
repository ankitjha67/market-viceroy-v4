# crack_spread — 3-2-1 Crack-Spread Mean Reversion

3-leg mean-reversion trade on the crude / gasoline / heating-oil
refining margin. Long the crack (long products, short crude) when
the rolling z-score is below -2σ; short the crack when z > +2σ;
flat when |z| < 0.5σ (hysteresis).

> Compute crack = 2 × RB + 1 × HO − 3 × CL daily. Rolling z-score
> over 252 days. Long when z < -2; short when z > +2. Per
> Girma-Paulson 1999 risk-arbitrage framework on the 3-2-1
> refining ratio (Geman 2005 §7).

## Quickstart

```python
from alphakit.strategies.commodity import CrackSpread
from alphakit.bridges import vectorbt_bridge
import pandas as pd

prices: pd.DataFrame = ...  # ["CL=F", "RB=F", "HO=F"]

strategy = CrackSpread()
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
| `crude_symbol` | `"CL=F"` | Crude leg |
| `gasoline_symbol` | `"RB=F"` | Gasoline leg |
| `heating_oil_symbol` | `"HO=F"` | Heating-oil leg |
| `zscore_lookback_days` | `252` | Rolling z-score window |
| `entry_threshold` | `2.0` | |z| to enter |
| `exit_threshold` | `0.5` | |z| to exit (hysteresis) |

The 3-2-1 ratio is hardcoded: per-leg weights 0.500 / 0.333 /
0.167 (sum |w| = 1) preserving the canonical refining ratio.

See [`config.yaml`](config.yaml) for the full default configuration
and [`strategy.py`](strategy.py) for the implementation docstring.

## Documentation

* [Foundational + primary citations](paper.md) — Geman (2005) §7
  refining-ratio textbook + Girma-Paulson (1999) mean-reversion
  empirical evidence
* [Known failure modes](known_failures.md) — structural-regime
  shifts (2008 H2 demand collapse, 2014-15 shale-glut, 2020 H1
  COVID), hurricane / refinery outages, RBOB transition (2006),
  multi-leg execution risk
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed yfinance-futures benchmark deferred to
  Session 2H.

## When to use this

`crack_spread` is the right choice when you want to **harvest the
refining-margin mean reversion premium** — a niche
risk-arbitrage trade that is largely uncorrelated with trend,
momentum, and curve-carry signals. Pairs naturally with
`crush_spread` (independent processing-margin trade) and
`wti_brent_spread` for a multi-spread book.

## Tests

```bash
uv run pytest packages/alphakit-strategies-commodity/alphakit/strategies/commodity/crack_spread/tests
```
