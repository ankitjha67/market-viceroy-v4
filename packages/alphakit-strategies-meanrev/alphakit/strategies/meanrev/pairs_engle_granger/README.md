# pairs_engle_granger — Engle-Granger Cointegration Pairs Trading (Engle & Granger 1987)

> Rolling OLS hedge ratio between each pair of assets; trade the
> spread when its Z-score exceeds a threshold. Cross-sectional
> strategy requiring at least 2 assets.

```python
from alphakit.strategies.meanrev import PairsEngleGranger

strategy = PairsEngleGranger(formation_period=252, zscore_lookback=20, threshold=2.0)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
