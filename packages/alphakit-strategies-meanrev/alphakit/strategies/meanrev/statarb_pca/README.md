# statarb_pca — Avellaneda-Lee PCA Stat Arb (Avellaneda & Lee 2010)

> PCA decomposition of returns into factor and residual components.
> Trade mean reversion of cumulative residuals.

```python
from alphakit.strategies.meanrev import StatArbPCA

strategy = StatArbPCA(n_factors=15, formation_period=252, threshold=2.0)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
