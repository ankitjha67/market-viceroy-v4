# Paper — The Cross-Section of Expected Stock Returns

> Fama, E.F. & French, K.R. (1992). The Cross-Section of Expected
> Stock Returns. *Journal of Finance*, 47(2), 427-465.
> DOI: 10.1111/j.1540-6261.1992.tb04398.x.

```bibtex
@article{fama1992cross,
  title   = {The Cross-Section of Expected Stock Returns},
  author  = {Fama, Eugene F. and French, Kenneth R.},
  journal = {Journal of Finance},
  volume  = {47},
  number  = {2},
  pages   = {427--465},
  year    = {1992},
  doi     = {10.1111/j.1540-6261.1992.tb04398.x}
}
```

## Summary

Fama and French demonstrate that two variables — market equity (size)
and book-to-market equity (B/M) — capture much of the cross-sectional
variation in average US stock returns. High B/M ("value") stocks earn
higher average returns than low B/M ("growth") stocks, even after
controlling for beta. The paper established B/M as the canonical
value factor.

This implementation uses a price-derived proxy per ADR-001: long-term
(3-year) price reversal stands in for the book-to-market ratio.
Stocks that have underperformed over 3 years tend to have low P/B
(high B/M), making trailing return a reasonable price-only proxy.

## Canonical parameters

| Parameter | Paper | AlphaKit default |
|---|---|---|
| Lookback (value proxy) | ~3 years | 756 days |
| Rebalance | annual (June) | monthly |
| Universe | NYSE/AMEX/NASDAQ | configurable |

## In-sample period

1963-1990 (US equities, CRSP/Compustat).
