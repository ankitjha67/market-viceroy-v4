# rsi_reversion_2 — Connors RSI(2) Mean Reversion (Connors & Alvarez 2009)

> Long when RSI(2) < 10 (deeply oversold); short when RSI(2) > 90
> (deeply overbought). Very short-term contrarian signal.

```python
from alphakit.strategies.meanrev import RSIReversion2

strategy = RSIReversion2(period=2, lower_threshold=10.0, upper_threshold=90.0)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
