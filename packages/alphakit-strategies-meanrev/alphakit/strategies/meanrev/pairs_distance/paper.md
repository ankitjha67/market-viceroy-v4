# Paper — Pairs Trading: Performance of a Relative-Value Arbitrage Rule

> Gatev, E., Goetzmann, W.N. & Rouwenhorst, K.G. (2006). Pairs
> Trading: Performance of a Relative-Value Arbitrage Rule. *Review
> of Financial Studies*, 19(3), 797-827. DOI: 10.1093/rfs/hhj020.

```bibtex
@article{gatev2006pairs,
  title     = {Pairs Trading: Performance of a Relative-Value Arbitrage Rule},
  author    = {Gatev, Evan and Goetzmann, William N. and Rouwenhorst, K. Geert},
  journal   = {Review of Financial Studies},
  volume    = {19},
  number    = {3},
  pages     = {797--827},
  year      = {2006},
  doi       = {10.1093/rfs/hhj020}
}
```

## Summary

The GGR distance method forms pairs by minimizing the sum of squared
deviations between normalized price series over a formation period.
During the trading period, when the spread between a pair exceeds a
threshold (measured in standard deviations), the strategy goes long
the underperformer and short the outperformer. The authors document
average annualized excess returns of up to 11% for the top pairs
portfolios, though returns have declined over time as the strategy
became more widely known.

## Canonical parameters

| Parameter        | Paper            | AlphaKit default |
|------------------|------------------|------------------|
| Formation period | 12 months (252d) | 252              |
| Z-score lookback | 20 days          | 20               |
| Entry threshold  | 2.0 sigma        | 2.0              |

## In-sample period

1962-2002 US equities (NYSE, AMEX, NASDAQ).
