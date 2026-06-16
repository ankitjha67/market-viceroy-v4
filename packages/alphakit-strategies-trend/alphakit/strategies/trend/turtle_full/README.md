# turtle_full — Full Turtle System (Faith 2003)

> Combines Donchian breakout System 1 (20/10) and System 2 (55/20).
> Per-asset weight is the average of the two systems' states,
> divided by the number of instruments in the universe.

```python
from alphakit.strategies.trend import TurtleFull
strategy = TurtleFull()
```

Phase 1 ships a simplified variant — no ATR sizing, no correlation
caps, no skip rule. See [`paper.md`](paper.md) for the full rule list
and [`known_failures.md`](known_failures.md) for the implications.
