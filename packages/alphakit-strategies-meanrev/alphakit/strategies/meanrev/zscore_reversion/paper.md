# Book — Algorithmic Trading: Winning Strategies and Their Rationale

> Chan, E.P. (2013). *Algorithmic Trading: Winning Strategies and
> Their Rationale*. Wiley. ISBN 978-1-118-46014-6.

```bibtex
@book{chan2013algorithmic,
  title     = {Algorithmic Trading: Winning Strategies and Their Rationale},
  author    = {Chan, Ernest P.},
  publisher = {Wiley},
  year      = {2013},
  isbn      = {978-1-118-46014-6}
}
```

## Summary

Chan presents the rolling Z-score as a simple and robust mean-reversion
signal. The Z-score normalizes price by its recent history: Z = (P − μ) / σ
where μ and σ are the rolling mean and standard deviation. When |Z| > 2,
the price is approximately 2 standard deviations from its recent mean and
statistically likely to revert.

## Canonical parameters

| Parameter | Chan | AlphaKit default |
|---|---|---|
| Lookback window | 20 days | 20 |
| Entry threshold | ±2σ | 2.0 |

## In-sample period

Chan tested on various US equity pairs and ETFs, 2006-2012.
