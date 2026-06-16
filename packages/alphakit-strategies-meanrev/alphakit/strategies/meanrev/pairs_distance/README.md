# pairs_distance — GGR Distance-Method Pairs Trading (Gatev et al. 2006)

> Long the underperformer, short the outperformer when normalized
> price spread exceeds a Z-score threshold. Cross-sectional strategy
> requiring at least 2 assets.

```python
from alphakit.strategies.meanrev import PairsDistance

strategy = PairsDistance(formation_period=252, zscore_lookback=20, threshold=2.0)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
