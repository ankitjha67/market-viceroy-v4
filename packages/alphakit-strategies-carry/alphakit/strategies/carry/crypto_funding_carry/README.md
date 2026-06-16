# crypto_funding_carry — Crypto Funding Rate Carry

> Per-asset threshold-based funding rate proxy strategy.
> Phase 1 uses fast/slow MA spread as funding proxy (see ADR-001).

```python
from alphakit.strategies.carry import CryptoFundingCarry

strategy = CryptoFundingCarry(fast_period=5, slow_period=30, threshold=0.005)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
