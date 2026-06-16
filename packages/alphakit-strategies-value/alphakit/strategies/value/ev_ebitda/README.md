# ev_ebitda — EV/EBITDA Value (Loughran & Wellman 2011)

> Cross-sectional long/short: buy cheap (low EV/EBITDA proxy), sell
> expensive (high EV/EBITDA proxy), dollar-neutral.

```python
from alphakit.strategies.value import EVEbitda

strategy = EVEbitda(lookback=756)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
