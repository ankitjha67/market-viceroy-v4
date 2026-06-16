# donchian_breakout_20 — 20-day Donchian Breakout (Donchian 1960)

> Long on a break above the trailing 20-day high. Short on a break
> below the 20-day low. Hold until the next breakout.

```python
from alphakit.strategies.trend import DonchianBreakout20
strategy = DonchianBreakout20(window=20)
```

See [`paper.md`](paper.md), [`known_failures.md`](known_failures.md).
