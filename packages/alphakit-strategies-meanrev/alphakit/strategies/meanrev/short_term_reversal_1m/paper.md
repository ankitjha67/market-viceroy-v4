# Paper — Evidence of Predictable Behavior of Security Returns

> Jegadeesh, N. (1990). Evidence of Predictable Behavior of Security
> Returns. *Journal of Finance*, 45(3), 881-898.
> DOI: 10.1111/j.1540-6261.1990.tb05088.x.

```bibtex
@article{jegadeesh1990evidence,
  title   = {Evidence of Predictable Behavior of Security Returns},
  author  = {Jegadeesh, Narasimhan},
  journal = {Journal of Finance},
  volume  = {45},
  number  = {3},
  pages   = {881--898},
  year    = {1990},
  doi     = {10.1111/j.1540-6261.1990.tb05088.x}
}
```

## Summary

Jegadeesh documents significant negative first-order serial
correlation in monthly stock returns. Stocks that performed worst
over the prior month tend to outperform in the next month, and vice
versa. The strategy ranks assets cross-sectionally by their trailing
1-month return, goes long the worst performers and short the best
performers. This is a pure cross-sectional reversal strategy that
requires at least two assets in the universe.

## Canonical parameters

| Parameter | Jegadeesh | AlphaKit default |
|---|---|---|
| Lookback period | 1 month (~21 trading days) | 21 |
| Holding period | 1 month | daily rebalance |

## In-sample period

Jegadeesh tested on NYSE/AMEX stocks 1934-1987.
