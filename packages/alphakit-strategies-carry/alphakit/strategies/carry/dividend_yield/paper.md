# Paper — The Effect of Personal Taxes and Dividends on Capital Asset Prices

> Litzenberger, R.H. & Ramaswamy, K. (1979). The effect of personal
> taxes and dividends on capital asset prices. *Journal of Financial
> Economics*, 7(2), 163-195. DOI: 10.1016/0304-405X(79)90012-6.

```bibtex
@article{litzenberger1979effect,
  title   = {The effect of personal taxes and dividends on capital asset prices},
  author  = {Litzenberger, Robert H. and Ramaswamy, Krishna},
  journal = {Journal of Financial Economics},
  volume  = {7},
  number  = {2},
  pages   = {163--195},
  year    = {1979},
  doi     = {10.1016/0304-405X(79)90012-6}
}
```

## Summary

Litzenberger and Ramaswamy show that stocks with higher dividend
yields earn higher pre-tax expected returns, consistent with a tax
clientele effect where investors demand compensation for the tax
disadvantage of dividends relative to capital gains. High-dividend-
yield stocks can be viewed as "high carry" assets in equities: the
dividend is analogous to the interest-rate differential in FX carry.
The strategy goes long high-yield stocks and short low-yield stocks.

## Phase 1 proxy

The StrategyProtocol provides only close prices, not dividend data.
This implementation uses the trailing 252-day return divided by
trailing volatility as a dividend yield proxy: assets with high
risk-adjusted returns are treated as "high dividend yield." This is
a known simplification (see ADR-001). The proxy conflates carry
with low-volatility effects. In production, replace with actual
dividend yield data.

## Canonical parameters

| Parameter | Litzenberger & Ramaswamy | AlphaKit default |
|---|---|---|
| Carry signal | Dividend yield | Trailing return / vol (proxy) |
| Lookback | N/A (cross-sectional) | 252 days |
| Universe | NYSE stocks | 6 ETFs (SPY, EFA, EEM, AGG, GLD, DBC) |

## In-sample period

Litzenberger & Ramaswamy tested on NYSE stocks, 1936-1977.
