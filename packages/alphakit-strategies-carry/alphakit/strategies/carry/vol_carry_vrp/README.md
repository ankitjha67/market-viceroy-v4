# vol_carry_vrp — Variance Risk Premium Carry (Carr & Wu 2009)

> Per-asset fast vs slow realized vol comparison as VRP proxy.
> Phase 1 uses fast/slow realized vol spread (see ADR-001).

```python
from alphakit.strategies.carry import VolCarryVRP

strategy = VolCarryVRP(fast_vol_window=5, slow_vol_window=20)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
