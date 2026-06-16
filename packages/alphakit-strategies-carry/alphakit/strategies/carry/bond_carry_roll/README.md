# bond_carry_roll — Bond Carry + Roll-Down (KMPV 2018)

> Cross-sectional rank by trailing return on sovereign bonds, dollar-neutral.
> Phase 1 uses trailing return as carry proxy (see ADR-001).

```python
from alphakit.strategies.carry import BondCarryRoll

strategy = BondCarryRoll(lookback=63)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
