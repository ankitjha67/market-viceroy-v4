# long_term_reversal — Long-Term Reversal (DeBondt & Thaler 1985)

> Cross-sectional contrarian: long past losers, short past winners
> over a 3-year lookback. Dollar-neutral, rebalanced monthly.

```python
from alphakit.strategies.meanrev import LongTermReversal

strategy = LongTermReversal(lookback_years=3)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
