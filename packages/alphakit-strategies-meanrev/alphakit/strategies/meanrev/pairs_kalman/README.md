# pairs_kalman — Kalman-Filtered Dynamic Hedge Ratio Pairs Trading (Chan 2013)

> Kalman filter dynamically estimates the hedge ratio between each
> pair; trade the spread when its Z-score exceeds a threshold.
> Cross-sectional strategy requiring at least 2 assets.

```python
from alphakit.strategies.meanrev import PairsKalman

strategy = PairsKalman(delta=1e-4, ve=1e-3, zscore_lookback=20, threshold=2.0)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
