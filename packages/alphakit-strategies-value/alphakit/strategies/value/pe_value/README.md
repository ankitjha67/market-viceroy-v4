# pe_value — Price-to-Earnings Value (Basu 1977)

> Cross-sectional long/short: buy cheap (low P/E proxy), sell
> expensive (high P/E proxy), dollar-neutral.

```python
from alphakit.strategies.value import PEValue

strategy = PEValue(lookback=756)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
