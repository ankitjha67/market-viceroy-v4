# ou_process_trade — Ornstein-Uhlenbeck Mean Reversion (Avellaneda & Lee 2010)

> Calibrates OU process parameters on rolling window, sizes positions
> by Z-score scaled inversely by half-life of mean reversion.

```python
from alphakit.strategies.meanrev import OUProcessTrade

strategy = OUProcessTrade(lookback=60, max_half_life=120)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
