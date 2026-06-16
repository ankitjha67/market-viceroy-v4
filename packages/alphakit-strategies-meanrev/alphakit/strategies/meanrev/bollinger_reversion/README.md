# bollinger_reversion — Bollinger Band Mean Reversion (Bollinger 2001)

> Long when price touches lower band (oversold); short when price
> touches upper band (overbought). Flat inside the bands.

```python
from alphakit.strategies.meanrev import BollingerReversion

strategy = BollingerReversion(period=20, num_std=2.0)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
