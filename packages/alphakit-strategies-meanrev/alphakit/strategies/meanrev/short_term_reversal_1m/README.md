# short_term_reversal_1m — Short-Term Cross-Sectional Reversal (Jegadeesh 1990)

> Long worst 1-month performers, short best 1-month performers.
> Pure cross-sectional reversal; requires at least 2 assets.

```python
from alphakit.strategies.meanrev import ShortTermReversal1M

strategy = ShortTermReversal1M(lookback=21)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
