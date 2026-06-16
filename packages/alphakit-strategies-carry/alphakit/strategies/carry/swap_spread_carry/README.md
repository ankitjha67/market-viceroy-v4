# swap_spread_carry — Swap Spread Carry (Duarte et al. 2007)

> Cross-sectional across rate tenors. Phase 1 uses trailing return as
> carry proxy (see ADR-001).

```python
from alphakit.strategies.carry import SwapSpreadCarry

strategy = SwapSpreadCarry(lookback=63)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
