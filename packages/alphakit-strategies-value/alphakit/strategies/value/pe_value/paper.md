# Paper — Investment Performance of Common Stocks in Relation to Their P/E Ratios

> Basu, S. (1977). Investment Performance of Common Stocks in Relation
> to Their Price-Earnings Ratios: A Test of the Efficient Market
> Hypothesis. *Journal of Finance*, 32(3), 663-682.
> DOI: 10.1111/j.1540-6261.1977.tb01979.x.

```bibtex
@article{basu1977investment,
  title   = {Investment Performance of Common Stocks in Relation to
             Their Price-Earnings Ratios: A Test of the Efficient
             Market Hypothesis},
  author  = {Basu, Sanjoy},
  journal = {Journal of Finance},
  volume  = {32},
  number  = {3},
  pages   = {663--682},
  year    = {1977},
  doi     = {10.1111/j.1540-6261.1977.tb01979.x}
}
```

## Summary

Basu shows that portfolios of low P/E stocks earn higher risk-adjusted
returns than high P/E portfolios, contradicting the semi-strong form
of the efficient market hypothesis. The earnings yield (E/P) effect
is one of the earliest documented value anomalies.

This implementation uses a price-derived proxy per ADR-001: long-term
(3-year) price reversal stands in for the earnings yield. Stocks with
low trailing returns tend to have high E/P (low P/E), making negative
trailing return a reasonable price-only proxy for cheapness.

## Canonical parameters

| Parameter | Paper | AlphaKit default |
|---|---|---|
| Lookback (value proxy) | ~1 year holding | 756 days |
| Rebalance | annual (April) | monthly |
| Universe | NYSE industrials | configurable |

## In-sample period

1957-1971 (NYSE industrial firms).
