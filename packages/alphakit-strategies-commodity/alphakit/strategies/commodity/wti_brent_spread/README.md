# wti_brent_spread — WTI-Brent Crude Oil Pairs Trading

2-leg pairs-trading mean-reversion on the WTI-Brent crude oil
spread. Long the spread (long WTI, short Brent) when the rolling
z-score is below -2σ; short the spread when z > +2σ; flat when
|z| < 0.5σ.

> Compute spread = CL − BZ daily. Rolling z-score over 252 days.
> Long when z < -2; short when z > +2. Per Gatev-Goetzmann-
> Rouwenhorst 2006 pairs-trading framework applied to the
> WTI-Brent cointegration documented in Reboredo 2011.

## Quickstart

```python
from alphakit.strategies.commodity import WTIBrentSpread
from alphakit.bridges import vectorbt_bridge
import pandas as pd

prices: pd.DataFrame = ...  # ["CL=F", "BZ=F"]

strategy = WTIBrentSpread()
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
| `wti_symbol` | `"CL=F"` | WTI leg |
| `brent_symbol` | `"BZ=F"` | Brent leg |
| `zscore_lookback_days` | `252` | Rolling z-score window |
| `entry_threshold` | `2.0` | |z| to enter |
| `exit_threshold` | `0.5` | |z| to exit (hysteresis) |

The 1:1 dollar-neutral pair structure is hardcoded: per-leg
weights ±0.5 (long-spread: CL=+0.5, BZ=-0.5; short-spread:
CL=-0.5, BZ=+0.5).

## Documentation

* [Foundational + primary citations](paper.md) — Gatev/
  Goetzmann/Rouwenhorst (2006) pairs-trading methodology +
  Reboredo (2011) WTI-Brent cointegration evidence; **explicit
  cointegration discussion** with the Engle-Granger β estimates
  per regime (pre-shale, Cushing-glut, post-export-ban)
* [Known failure modes](known_failures.md) — **2011-2014
  Cushing-glut cointegration break (largest historical
  failure, ~28% drawdown)**, geopolitical shocks (2014 Libya,
  2019 Saudi attacks, 2022 Russia), Cushing-storage capacity
  events (April 2020 negative WTI price), ICE Brent contract
  specifics
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed yfinance-futures benchmark deferred to
  Session 2H.

## When to use this

`wti_brent_spread` is the right choice when you want to **harvest
the geographic-arbitrage premium** between US (Cushing) and
European (North Sea) crude markets — a niche risk-arbitrage trade
that is largely uncorrelated with directional crude exposure.
Pairs naturally with `crack_spread` and `crush_spread` for a
multi-spread book.

**Important caveat**: the strategy assumes WTI-Brent
cointegration holds, which has empirically broken in two
extended episodes (2011-2014 Cushing-glut, briefly 2022 H1
Russia sanctions). Real-money users should overlay an explicit
cointegration test that disables trading when the ADF p-value
on the residual exceeds 0.10. This is a Phase 3 enhancement.

## Tests

```bash
uv run pytest packages/alphakit-strategies-commodity/alphakit/strategies/commodity/wti_brent_spread/tests
```
