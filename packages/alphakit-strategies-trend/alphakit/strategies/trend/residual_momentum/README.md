# residual_momentum — Residual Cross-Sectional Momentum (Blitz et al. 2011)

> Same as `xs_momentum_jt`, but rank on market-hedged residuals instead
> of total returns. Phase 1 ships the single-factor market-hedged
> variant; Phase 4 will add the full Fama-French 3-factor variant as
> `residual_momentum_ff3`.

## Quickstart

```python
from alphakit.strategies.trend import ResidualMomentum
from alphakit.bridges import vectorbt_bridge
import pandas as pd

prices: pd.DataFrame = ...
strategy = ResidualMomentum(formation_months=12, top_pct=0.1)
result = vectorbt_bridge.run(strategy=strategy, prices=prices)
```

## Parameters

Same as `xs_momentum_jt` (formation_months, skip_months, top_pct,
long_only, min_positions_per_side). The key difference is the signal:
here we rank by cumulative residual return, not total return.

See [`paper.md`](paper.md) (especially the "Implementation deviations"
section), [`known_failures.md`](known_failures.md), and
[`config.yaml`](config.yaml).
