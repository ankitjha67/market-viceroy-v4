# ema_cross_12_26 — MACD Trigger (Appel 2005)

> Long each asset when EMA(12) > EMA(26); short when below. Default
> is long/short. Same multi-asset weighting convention as the SMA
> variants.

```python
from alphakit.strategies.trend import EMACross1226

strategy = EMACross1226(fast_span=12, slow_span=26)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
