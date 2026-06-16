# Paper — New Evidence on the Relation Between the Enterprise Multiple and Average Stock Returns

> Loughran, T. & Wellman, J.W. (2011). New Evidence on the Relation
> Between the Enterprise Multiple and Average Stock Returns. *Journal
> of Financial and Quantitative Analysis*, 46(6), 1693-1717.
> DOI: 10.1017/S0022109011000305.

```bibtex
@article{loughran2011enterprise,
  title   = {New Evidence on the Relation Between the Enterprise
             Multiple and Average Stock Returns},
  author  = {Loughran, Tim and Wellman, Jay W.},
  journal = {Journal of Financial and Quantitative Analysis},
  volume  = {46},
  number  = {6},
  pages   = {1693--1717},
  year    = {2011},
  doi     = {10.1017/S0022109011000305}
}
```

## Summary

Loughran and Wellman show that the enterprise multiple (EV/EBITDA) is
a strong predictor of the cross-section of average stock returns,
dominating B/M, E/P, and CF/P in head-to-head comparisons. Low
EV/EBITDA (cheap) firms earn significantly higher returns than high
EV/EBITDA (expensive) firms.

This implementation uses a price-derived proxy per ADR-001: long-term
(3-year) price reversal stands in for the EBITDA/EV ratio. Stocks
that have underperformed over 3 years tend to have lower enterprise
valuations relative to operating earnings.

## Canonical parameters

| Parameter | Paper | AlphaKit default |
|---|---|---|
| Lookback (value proxy) | annual rebalance | 756 days |
| Rebalance | annual (June) | monthly |
| Universe | NYSE/AMEX/NASDAQ non-financial | configurable |

## In-sample period

1963-2008 (US equities, Compustat).
