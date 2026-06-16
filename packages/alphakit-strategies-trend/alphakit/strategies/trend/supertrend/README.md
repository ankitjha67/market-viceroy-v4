# supertrend — Supertrend ATR Trailing Stop

> Long when close breaks above `close + 3 × ATR`; short when close
> breaks below `close − 3 × ATR`. Between flips, state persists.

```python
from alphakit.strategies.trend import Supertrend
strategy = Supertrend(atr_period=10, multiplier=3.0)
```

Citation is Wilder (1978) for the ATR primitive; Supertrend itself
is practitioner folklore with no formal paper. See [`paper.md`](paper.md)
for the honest attribution.
