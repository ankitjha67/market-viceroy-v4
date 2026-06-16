# Book — Bollinger on Bollinger Bands

> Bollinger, J. (2001). *Bollinger on Bollinger Bands*.
> McGraw-Hill. ISBN 0-07-137368-3.

```bibtex
@book{bollinger2001bands,
  title     = {Bollinger on Bollinger Bands},
  author    = {Bollinger, John},
  publisher = {McGraw-Hill},
  year      = {2001},
  isbn      = {0-07-137368-3}
}
```

## Summary

Bollinger Bands wrap a simple moving average with an upper and lower
envelope at ±k standard deviations. The canonical parameters are
SMA(20) ± 2σ. About 95% of price action stays within the bands under
a normal distribution assumption. The mean-reversion variant buys when
price touches the lower band (statistically oversold) and sells when
price touches the upper band (statistically overbought).

Bollinger himself cautions that the bands are not mechanical buy/sell
signals — they describe *relative* high and low. This implementation
uses the pure mechanical interpretation for systematic backtesting.

## Canonical parameters

| Parameter | Bollinger | AlphaKit default |
|---|---|---|
| SMA period | 20 | 20 |
| Standard deviations (k) | 2.0 | 2.0 |

## In-sample period

Bollinger developed the indicator in the early 1980s on US equities.
No formal academic in-sample period.
