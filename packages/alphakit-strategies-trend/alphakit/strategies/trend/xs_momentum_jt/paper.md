# Paper — Returns to Buying Winners and Selling Losers

## Citation

> Jegadeesh, N. & Titman, S. (1993).
> **Returns to buying winners and selling losers: implications for stock market efficiency.**
> *The Journal of Finance*, 48(1), 65–91.
> [https://doi.org/10.1111/j.1540-6261.1993.tb04702.x](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x)

```bibtex
@article{jegadeesh1993returns,
  title   = {Returns to buying winners and selling losers: Implications for stock market efficiency},
  author  = {Jegadeesh, Narasimhan and Titman, Sheridan},
  journal = {The Journal of Finance},
  volume  = {48},
  number  = {1},
  pages   = {65--91},
  year    = {1993},
  doi     = {10.1111/j.1540-6261.1993.tb04702.x}
}
```

## Abstract

> This paper documents that strategies which buy stocks that have
> performed well in the past and sell stocks that have performed
> poorly in the past generate significant positive returns over 3- to
> 12-month holding periods. We find that the profitability of these
> strategies are not due to their systematic risk or to delayed stock
> price reactions to common factors. However, part of the abnormal
> returns generated in the first year after portfolio formation
> dissipates in the following two years.

## Published parameters

| Parameter | Paper | AlphaKit default |
|---|---|---|
| Formation (J) | 3, 6, 9, 12 months | 6 months |
| Holding (K) | 3, 6, 9, 12 months | 6 months (via monthly rebalance) |
| Skip (gap) | 0 (original), 1 (later literature) | 1 month |
| Long/short decile | 10%, NYSE/AMEX universe | `top_pct=0.1` |
| Rebalance | monthly overlapping | monthly non-overlapping |

## In-sample period

* 1965–1989 CRSP NYSE/AMEX common stocks.

## Known replications

* Grinblatt & Moskowitz (2004). "Predicting stock price movements from past returns". JFE.
* Lewellen, J. (2002). "Momentum and autocorrelation in stock returns". RFS.
* Asness, Moskowitz & Pedersen (2013). "Value and momentum everywhere". JF.

## Implementation deviations

1. **1-month skip** (vs. original 0) to avoid the Jegadeesh (1990)
   short-term reversal contamination. Nearly every paper since 1993
   uses this convention.
2. **Non-overlapping** monthly rebalance. JT (1993) use overlapping
   portfolios that average K independent positions; the non-overlapping
   version is simpler and preserves the sign and sign-weighted
   performance of the overlapping variant.
3. **`min_positions_per_side=1`** keeps the strategy defined on small
   ETF universes.
