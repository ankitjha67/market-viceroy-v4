# yield_curve_pca_trade — PCA-Residual Mean-Reversion on Treasury Curve

Cross-sectional dollar-neutral mean-reversion on the residual after
projecting bond returns onto the top-3 PCs of a rolling covariance
fit. Citation: Litterman & Scheinkman (1991) — three principal
components (level, slope, curvature) explain ~99% of yield-curve
variance; anything unexplained is idiosyncratic and mean-reverting.

> Long the bond with the most negative rolling residual, short the
> one with the most positive. Rebalance monthly. Rolling 24-month
> PCA fit, 3-month residual accumulation.

## Quickstart

```python
from alphakit.strategies.rates import YieldCurvePCATrade
from alphakit.bridges import vectorbt_bridge
import pandas as pd

# N>=4 column bond proxy panel.
prices: pd.DataFrame = ...   # e.g. ["SHY", "IEI", "IEF", "TLH", "TLT"]

strategy = YieldCurvePCATrade()
result = vectorbt_bridge.run(
    strategy=strategy,
    prices=prices,
    initial_cash=100_000,
    commission_bps=2,
)
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `n_pcs` | `3` | Top PCs to strip (level, slope, curvature) |
| `pca_window_months` | `24` | Rolling window for the PCA fit |
| `residual_lookback_months` | `3` | Residual accumulation horizon |

## Documentation

* [Citation](paper.md) — Litterman/Scheinkman (1991) PCA framework;
  algorithm walk-through; implementation deviations.
* [Known failure modes](known_failures.md) — regime change inside
  fit window, PCA over-fit on small panels, non-mean-reverting
  residuals during liquidity stress, cluster overlap with
  `curve_butterfly_2s5s10s`.
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed FRED DGS2/3/5/7/10/20/30 benchmark
  deferred to Session 2H.
