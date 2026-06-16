# Paper — High Finance in Copper (Donchian 1960)

> Donchian, R. D. (1960). *High Finance in Copper*.
> *Financial Analysts Journal*, 16(6), 133–142.
> [DOI](https://doi.org/10.2469/faj.v16.n6.133)

```bibtex
@article{donchian1960high,
  title   = {High Finance in Copper},
  author  = {Donchian, Richard D.},
  journal = {Financial Analysts Journal},
  volume  = {16},
  number  = {6},
  pages   = {133--142},
  year    = {1960},
  doi     = {10.2469/faj.v16.n6.133}
}
```

## Summary

Richard Donchian was one of the earliest systematic trend-followers.
His FAJ article lays out the case for using the *highest high* and
*lowest low* over a recent window as a trend signal: break above the
window's high → long, break below → short. He tested it on copper
futures from the 1950s and reported consistent profitability. The
Donchian channel (the area between the rolling max and min) is now
a standard technical-analysis indicator in every charting package.

## Canonical windows

* **20 days** — short-term breakout (AlphaKit default for this strategy)
* **55 days** — medium-term breakout (ships as `donchian_breakout_55`)
* **5 / 20 days** — System 1 of the Dennis Turtle system (`turtle_full`)

## In-sample period

* 1950s copper futures (Donchian's original column).
* Subsequent practitioner use spans 1960–present across all futures
  markets.
