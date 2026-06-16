# Paper — Does the Stock Market Overreact?

> DeBondt, W.F.M. & Thaler, R. (1985). Does the Stock Market
> Overreact? *Journal of Finance*, 40(3), 793-805.
> DOI: 10.1111/j.1540-6261.1985.tb05004.x.

```bibtex
@article{debondt1985overreact,
  title     = {Does the Stock Market Overreact?},
  author    = {DeBondt, Werner F.M. and Thaler, Richard},
  journal   = {Journal of Finance},
  volume    = {40},
  number    = {3},
  pages     = {793--805},
  year      = {1985},
  doi       = {10.1111/j.1540-6261.1985.tb05004.x}
}
```

## Summary

DeBondt and Thaler demonstrated that stocks with extreme past
performance over 3-5 years exhibit mean reversion. Portfolios of
past "losers" (stocks with the worst trailing returns) subsequently
outperform past "winners" (stocks with the best trailing returns).
This effect is attributed to investor overreaction — market
participants extrapolate past performance too far into the future,
causing prices to overshoot fundamental value.

The strategy constructs a dollar-neutral portfolio: long the worst
trailing-return decile, short the best trailing-return decile.
Rebalancing occurs monthly.

## Canonical parameters

| Parameter | DeBondt & Thaler | AlphaKit default |
|---|---|---|
| Lookback period | 3-5 years | 3 years |
| Rebalance frequency | Annual | Monthly |
| Portfolio construction | Decile long/short | Rank-weighted L/S |

## In-sample period

NYSE stocks, 1926-1982.
