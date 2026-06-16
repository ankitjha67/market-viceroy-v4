# Book — Technical Analysis: Power Tools for Active Investors

> Appel, G. (2005). *Technical Analysis: Power Tools for Active
> Investors*. Financial Times Prentice Hall. ISBN 978-0131479029.

```bibtex
@book{appel2005technical,
  title     = {Technical Analysis: Power Tools for Active Investors},
  author    = {Appel, Gerald},
  publisher = {Financial Times Prentice Hall},
  year      = {2005},
  isbn      = {978-0131479029}
}
```

## Summary

Gerald Appel introduced the MACD indicator in the late 1970s. The
canonical parameters — fast EMA span of 12 periods, slow EMA span of
26 periods, signal-line smoothing span of 9 periods — have been used
without modification on trading screens and charting software ever
since. This strategy ships the **naked** EMA cross (the "MACD line"
crossing zero), which fires on average ~20% more often than the
smoothed signal-line cross and is the signal Appel himself prefers
for trend identification (the signal-line cross is reserved for
trigger timing).

A smoothed-signal-line variant (`ema_cross_macd_signal`) will ship
in Phase 4 when the family includes indicators that need to reference
the difference histogram (``MACD − signal``).

## Canonical parameters

| Parameter | Appel | AlphaKit default |
|---|---|---|
| Fast EMA span | 12 | 12 |
| Slow EMA span | 26 | 26 |
| Signal-line span | 9 | n/a (Phase 4) |

## In-sample period

Originally developed on US stock indices in the 1970s. No academic
in-sample period; the rule is practitioner lore.
