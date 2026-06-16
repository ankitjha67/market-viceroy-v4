# Paper — A Tug of War: Overnight Versus Intraday Expected Returns

> Lou, D., Polk, C. & Skouras, S. (2019). A Tug of War: Overnight
> Versus Intraday Expected Returns. *Journal of Financial Economics*,
> 134(1), 192-213. DOI: 10.1016/j.jfineco.2018.11.007.

```bibtex
@article{lou2019tugofwar,
  title     = {A Tug of War: Overnight Versus Intraday Expected Returns},
  author    = {Lou, Dong and Polk, Christopher and Skouras, Spyros},
  journal   = {Journal of Financial Economics},
  volume    = {134},
  number    = {1},
  pages     = {192--213},
  year      = {2019},
  doi       = {10.1016/j.jfineco.2018.11.007}
}
```

## Summary

Lou, Polk, and Skouras document that overnight and intraday returns
exhibit opposite-signed autocorrelation. Stocks with high overnight
returns tend to revert intraday, and vice versa. The authors attribute
this to different investor clienteles trading at different times:
informed institutional trading dominates the close-to-open period,
while noise trading dominates intraday.

This implementation approximates the overnight component using
cross-sectional residuals (idiosyncratic return after removing the
market-wide move) and trades the reversal cross-sectionally: long
stocks with the worst trailing overnight scores, short those with
the best.

## Canonical parameters

| Parameter | Lou et al. | AlphaKit default |
|---|---|---|
| Lookback window | 20 days | 20 |
| Rebalance frequency | Daily | Daily |
| Portfolio construction | Decile long/short | Rank-weighted L/S |

## In-sample period

US equities (CRSP), 1993-2013.
