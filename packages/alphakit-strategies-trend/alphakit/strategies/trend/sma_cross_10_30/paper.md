# Paper — Simple Technical Trading Rules (Brock, Lakonishok, LeBaron 1992)

> Brock, W., Lakonishok, J. & LeBaron, B. (1992).
> **Simple technical trading rules and the stochastic properties of
> stock returns.** *The Journal of Finance*, 47(5), 1731–1764.
> [https://doi.org/10.1111/j.1540-6261.1992.tb04681.x](https://doi.org/10.1111/j.1540-6261.1992.tb04681.x)

```bibtex
@article{brock1992simple,
  title   = {Simple technical trading rules and the stochastic properties of stock returns},
  author  = {Brock, William and Lakonishok, Josef and LeBaron, Blake},
  journal = {The Journal of Finance},
  volume  = {47},
  number  = {5},
  pages   = {1731--1764},
  year    = {1992},
  doi     = {10.1111/j.1540-6261.1992.tb04681.x}
}
```

## Summary

BLL (1992) is the standard academic reference for simple moving-
average trading rules. They test 26 rule variants (VMA, FMA,
trading-range-break) against a bootstrap null distribution on the
Dow Jones Industrial Average from 1897 to 1986 and find statistically
significant positive excess returns for the fast-over-slow crossover
family, with the effect robust across subsample periods. The paper
kicked off a decade of academic follow-up work on technical analysis.

## Canonical (fast, slow) pairs from the paper

* 1 / 50
* 1 / 150
* 1 / 200
* **5 / 150** ← "VMA 5-150" is their headline rule
* 2 / 200
* **10 / 30** ← AlphaKit default for this strategy
* **50 / 200** ← also ships as `sma_cross_50_200`

## In-sample period

* 1897–1986 Dow Jones daily close.

## Known replications / follow-ups

* Sullivan, Timmermann & White (1999). *Data snooping, technical
  trading rule performance, and the bootstrap*. JF.
* Bessembinder & Chan (1995). *The profitability of technical trading
  rules in the Asian stock markets*. Pacific-Basin Finance Journal.

## Implementation deviations

None beyond the Phase 1 multi-asset convention: each asset gets
``sign(fast − slow) / n_symbols`` weight, so the gross book is 1.0
when every asset is aligned. BLL tested single-asset (Dow) only.
