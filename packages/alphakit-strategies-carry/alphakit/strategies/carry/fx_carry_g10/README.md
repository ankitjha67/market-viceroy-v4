# fx_carry_g10 — FX Carry Trade, G10 Currencies (Lustig et al. 2011)

> Long top 3 high-yield G10 currencies, short bottom 3 low-yield.
> Phase 1 uses trailing return as carry proxy (see ADR-001).

```python
from alphakit.strategies.carry import FXCarryG10

strategy = FXCarryG10(lookback=63, n_long=3, n_short=3)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
