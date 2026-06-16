# zscore_reversion — Rolling Z-Score Mean Reversion (Chan 2013)

> Long when 20-day Z-score ≤ −2σ (undervalued); short when Z-score
> ≥ +2σ (overvalued). Simple statistical mean reversion.

```python
from alphakit.strategies.meanrev import ZScoreReversion

strategy = ZScoreReversion(lookback=20, threshold=2.0)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
