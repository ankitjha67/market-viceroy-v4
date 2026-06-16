# Book — Short Term Trading Strategies That Work

> Connors, L. & Alvarez, C. (2009). *Short Term Trading Strategies
> That Work*. TradingMarkets. ISBN 978-0-9819239-0-0.

```bibtex
@book{connors2009short,
  title     = {Short Term Trading Strategies That Work},
  author    = {Connors, Larry and Alvarez, Cesar},
  publisher = {TradingMarkets},
  year      = {2009},
  isbn      = {978-0-9819239-0-0}
}
```

## Summary

Connors and Alvarez demonstrate that a 2-period RSI is a powerful
short-term mean-reversion signal. When RSI(2) drops below 10, the
asset is deeply oversold on a 2-day basis and has a statistical
tendency to bounce. When RSI(2) rises above 90, the asset is deeply
overbought and tends to pull back.

The key insight is that a very short RSI window (2 vs. Wilder's 14)
captures extreme 1-2 day moves that are more likely to revert than
persist. The strategy works best on liquid equities and ETFs.

## Canonical parameters

| Parameter | Connors | AlphaKit default |
|---|---|---|
| RSI period | 2 | 2 |
| Buy threshold | < 10 | 10 |
| Sell threshold | > 90 | 90 |

## In-sample period

Connors tested on US equities 1995-2007.
