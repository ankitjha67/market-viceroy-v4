# repo_carry — Repo Carry (Duffie 1996)

> GC vs special repo rate arbitrage proxy. Phase 1 uses Z-score as
> specialness proxy (see ADR-001).

```python
from alphakit.strategies.carry import RepoCarry

strategy = RepoCarry(lookback=60, threshold=1.0)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
