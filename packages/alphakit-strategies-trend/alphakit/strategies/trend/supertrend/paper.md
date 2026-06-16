# Reference — Supertrend

## Primary citation (ATR primitive)

> Wilder, J. W. (1978). *New Concepts in Technical Trading Systems*.
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

## Citation honesty

**Supertrend itself has no formal academic citation.** The indicator
was popularised in French trading publications around 2005 (Olivier
Seban's *Money Trend System* and derivatives) and later entered the
TradingView community stock library, but no peer-reviewed paper
isolates its alpha from that of simpler ATR-based trailing-stop
schemes.

What Supertrend *is* built on is Wilder's ATR (Average True Range),
which is rigorously defined in Wilder (1978) and is the canonical
primitive for volatility-aware stops. We cite Wilder 1978 as the
closest verifiable reference. Phase 4 may add a formal citation if
a peer-reviewed study of Supertrend emerges.

## Algorithm in brief

1. Compute ATR (close-only simplification: rolling mean of
   ``|close[t] − close[t-1]|``).
2. Bands at ``close ± multiplier * atr``.
3. State flips long when close crosses above the prior upper band;
   flips short when it crosses below the prior lower band.

Standard parameters: ``period=10, multiplier=3`` (the TradingView
default).

## In-sample period

None known. The rule is practitioner folklore.
