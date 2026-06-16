# Book — New Concepts in Technical Trading Systems

> Wilder, J.W. (1978). *New Concepts in Technical Trading Systems*.
> Trend Research. ISBN 0-89459-027-8.

```bibtex
@book{wilder1978new,
  title     = {New Concepts in Technical Trading Systems},
  author    = {Wilder, J. Welles},
  publisher = {Trend Research},
  year      = {1978},
  isbn      = {0-89459-027-8}
}
```

## Summary

Wilder's Relative Strength Index (RSI) compares the magnitude of
recent gains to recent losses over a 14-period window. The indicator
oscillates between 0 and 100. Readings above 70 indicate overbought
conditions; readings below 30 indicate oversold. This is the original
formulation and remains the most widely used RSI parameterization.

Unlike the aggressive RSI(2) variant, the 14-period window filters
out 1-2 day noise and captures multi-week overbought/oversold states.

## Canonical parameters

| Parameter | Wilder | AlphaKit default |
|---|---|---|
| RSI period | 14 | 14 |
| Overbought | 70 | 70 |
| Oversold | 30 | 30 |

## In-sample period

Wilder developed the indicator on commodity futures in the 1970s.
