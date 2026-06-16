# pairs_johansen — Johansen Multi-Asset Cointegration (Johansen 1991)

> Multi-asset cointegration via eigendecomposition. Finds the most
> stationary linear combination and trades its mean reversion.

```python
from alphakit.strategies.meanrev import PairsJohansen

strategy = PairsJohansen(formation_period=252, threshold=2.0)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
