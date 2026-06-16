# rsi_reversion_14 — Wilder RSI(14) Mean Reversion (Wilder 1978)

> Long when RSI(14) < 30 (oversold); short when RSI(14) > 70
> (overbought). Classic Wilder parameterization.

```python
from alphakit.strategies.meanrev import RSIReversion14

strategy = RSIReversion14(period=14, lower_threshold=30.0, upper_threshold=70.0)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
