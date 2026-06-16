# Book — Trading with Ichimoku Clouds (Patel 2010)

> Patel, P. (2010). *Trading with Ichimoku Clouds: The Essential Guide
> to Ichimoku Kinko Hyo Technical Analysis*. Wiley.
> ISBN 978-0470609941.

```bibtex
@book{patel2010trading,
  title     = {Trading with Ichimoku Clouds: The Essential Guide to Ichimoku Kinko Hyo Technical Analysis},
  author    = {Patel, Patrick},
  publisher = {Wiley},
  year      = {2010},
  isbn      = {978-0470609941}
}
```

Originally developed by Goichi Hosoda in 1930s Japan and published
in 1969. The system uses five lines computed from high/low over
three windows (9, 26, 52), projected forward to build a "cloud"
(``kumo``) that acts as dynamic support / resistance. Patel 2010 is
the canonical English-language practitioner reference.

## Standard parameters (unchanged since Hosoda 1969)

| Parameter | Value | Meaning |
|---|---|---|
| Tenkan-sen window | 9 | conversion line period |
| Kijun-sen window | 26 | base line period |
| Senkou Span B window | 52 | slow line period |
| Cloud projection | +26 bars | forward displacement |

## Implementation deviation

AlphaKit uses close-only data so high and low in the Ichimoku
formulas are replaced with rolling max/min of close. On daily bars
for liquid instruments the sign of the cloud crossing matches the
OHLC version > 95% of the time.
