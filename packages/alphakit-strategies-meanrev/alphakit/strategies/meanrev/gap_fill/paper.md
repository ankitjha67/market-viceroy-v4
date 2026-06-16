# Paper — Simple Technical Trading Rules and the Stochastic Properties of Stock Returns

> Brock, W., Lakonishok, J. & LeBaron, B. (1992). Simple Technical
> Trading Rules and the Stochastic Properties of Stock Returns.
> *Journal of Finance*, 47(5), 1731-1764.
> DOI: 10.1111/j.1540-6261.1992.tb04681.x.

```bibtex
@article{brock1992simple,
  title     = {Simple Technical Trading Rules and the Stochastic Properties of Stock Returns},
  author    = {Brock, William and Lakonishok, Josef and LeBaron, Blake},
  journal   = {Journal of Finance},
  volume    = {47},
  number    = {5},
  pages     = {1731--1764},
  year      = {1992},
  doi       = {10.1111/j.1540-6261.1992.tb04681.x}
}
```

## Summary

Brock, Lakonishok, and LeBaron evaluated simple technical trading
rules — including moving averages and trading range breakouts — on
the Dow Jones Industrial Average from 1897 to 1986. They found that
buy signals consistently generated higher returns than sell signals,
and that these results were robust to various sub-periods and after
accounting for transaction costs.

The gap fill strategy is a practitioner extension of these ideas:
when price "gaps" away from the prior close by more than a threshold
number of standard deviations, it tends to partially revert. This
implementation computes a rolling Z-score of daily returns and fades
extreme moves (long after large negative gaps, short after large
positive gaps).

## Canonical parameters

| Parameter | BLL (1992) | AlphaKit default |
|---|---|---|
| Lookback window | 20 days | 20 |
| Gap threshold (σ) | N/A | 2.0 |
| Rebalance frequency | Daily | Daily |

## In-sample period

Dow Jones Industrial Average, 1897-1986.
