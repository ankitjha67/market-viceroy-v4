# overnight_intraday — Overnight vs. Intraday Reversal (Lou, Polk & Skouras 2019)

> Cross-sectional reversal on trailing overnight residual scores.
> Long worst overnight performers, short best. Daily rebalance.

```python
from alphakit.strategies.meanrev import OvernightIntraday

strategy = OvernightIntraday(lookback=20)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
