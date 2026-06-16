# equity_carry — Equity Carry (Koijen, Moskowitz, Pedersen & Vrugt 2018)

> Cross-sectional rank by trailing return, dollar-neutral.
> Phase 1 uses trailing return as carry proxy (see ADR-001).

```python
from alphakit.strategies.carry import EquityCarry

strategy = EquityCarry(lookback=252)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
