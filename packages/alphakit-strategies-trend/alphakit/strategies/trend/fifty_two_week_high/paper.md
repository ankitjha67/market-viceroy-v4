# Paper — The 52-Week High and Momentum Investing

## Citation

> George, T. J. & Hwang, C.-Y. (2004).
> **The 52-week high and momentum investing.**
> *The Journal of Finance*, 59(5), 2145–2176.
> [https://doi.org/10.1111/j.1540-6261.2004.00695.x](https://doi.org/10.1111/j.1540-6261.2004.00695.x)

```bibtex
@article{george2004fifty,
  title   = {The 52-week high and momentum investing},
  author  = {George, Thomas J and Hwang, Chuan-Yang},
  journal = {The Journal of Finance},
  volume  = {59},
  number  = {5},
  pages   = {2145--2176},
  year    = {2004},
  doi     = {10.1111/j.1540-6261.2004.00695.x}
}
```

## Abstract

> When coupled with a stock's current price, a readily available
> piece of information — the 52-week high price — explains a large
> portion of the profits from momentum investing. Near the 52-week
> high, traders are unwilling to bid the price of the stock higher
> even if the information warrants it. The information eventually
> prevails and the price moves up, resulting in a continuation.

## Published parameters

| Parameter | Paper | AlphaKit default |
|---|---|---|
| Window | 52 weeks (252 days) | `lookback_weeks=52` |
| Decile cut | 10% | `top_pct=0.1` |
| Rebalance | monthly | monthly |
| Holding period | 6 months overlapping | 1 month non-overlapping |

## Implementation deviation

Non-overlapping monthly holding, same convention as `xs_momentum_jt`.

## In-sample period

* 1963–2001 CRSP stocks.
