# sma_cross_50_200 — Golden Cross (BLL 1992)

> Long each asset when its 50-day SMA is above its 200-day SMA; flat
> otherwise. Default is long-only (binary equity-exposure switch).

```python
from alphakit.strategies.trend import SMACross50200

strategy = SMACross50200()  # long_only=True by default
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
