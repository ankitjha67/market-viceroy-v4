# pb_value — Price-to-Book Value (Fama & French 1992)

> Cross-sectional long/short: buy cheap (low P/B proxy), sell
> expensive (high P/B proxy), dollar-neutral.

```python
from alphakit.strategies.value import PBValue

strategy = PBValue(lookback=756)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).
