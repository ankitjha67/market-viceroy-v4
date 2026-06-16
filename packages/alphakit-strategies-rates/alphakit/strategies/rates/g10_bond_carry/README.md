# g10_bond_carry — G10 Cross-Country Sovereign Bond Carry

Cross-sectional dollar-neutral carry on G10 sovereign bond proxies.
Per Asness, Moskowitz & Pedersen (2013) §V: long the top-carry
country bonds, short the bottom-carry. Trailing 3-month return as
carry proxy. Optional per-country duration normalisation.

> Long the highest-carry country bond, short the lowest. Rebalance
> monthly. Dollar-neutral (weights sum to zero).

The trio (`bond_carry_roll`, `g10_bond_carry`, `bond_carry_rolldown`)
spans US-cross-section, G10-cross-section and US-time-series carry
respectively.

## Quickstart

```python
from alphakit.strategies.rates import G10BondCarry
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# N>=2 column G10 sovereign bond proxy panel.
prices: pd.DataFrame = ...   # e.g. ["BWX", "IGOV", "LEMB"]

strategy = G10BondCarry()
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
| `lookback_months` | `3` | trailing window for carry proxy |
| `durations` | `None` | optional per-country modified duration |

## Documentation

* [Citation](paper.md) — Asness/Moskowitz/Pedersen (2013) §V;
  cross-country bond carry sleeve. Explicit differentiation from
  US-only `bond_carry_roll` and time-series `bond_carry_rolldown`.
* [Known failure modes](known_failures.md) — funding-currency
  shocks (2008-09 GFC, 2022 USD strength), trailing-return-proxy
  vs explicit-carry mismatch, fixture-vs-real-data gap (US-only
  fallback), liquidity differentials.
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics with US-only fallback universe. **Real-feed
  Session 2H benchmark with FX-hedged G10 sovereign bonds is
  required for meaningful evaluation.**
