# dividend_yield — Dividend Yield Carry (Litzenberger & Ramaswamy 1979)

> Cross-sectional long/short on dividend yield proxy.
> Phase 1 uses trailing return / trailing volatility as proxy (see ADR-001).

```python
from alphakit.strategies.carry import DividendYield

strategy = DividendYield(lookback=252)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
