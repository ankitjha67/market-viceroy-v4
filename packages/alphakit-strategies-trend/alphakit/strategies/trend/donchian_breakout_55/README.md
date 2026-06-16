# donchian_breakout_55 — 55/20 Donchian Breakout (Turtle System 2)

> Long on break above the 55-day high; exit on break below the 20-day
> low. Short is symmetric. Slow, patient, whipsaw-resistant.

```python
from alphakit.strategies.trend import DonchianBreakout55
strategy = DonchianBreakout55()
```

See [`paper.md`](paper.md), [`known_failures.md`](known_failures.md).
