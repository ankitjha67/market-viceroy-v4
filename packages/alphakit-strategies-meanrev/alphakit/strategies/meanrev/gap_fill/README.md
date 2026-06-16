# gap_fill — Opening Gap Fill Mean Reversion (Brock, Lakonishok & LeBaron 1992)

> Fade large overnight gaps: long after oversized negative gaps,
> short after oversized positive gaps. Per-asset, daily rebalance.

```python
from alphakit.strategies.meanrev import GapFill

strategy = GapFill(lookback=20, gap_threshold=2.0)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
