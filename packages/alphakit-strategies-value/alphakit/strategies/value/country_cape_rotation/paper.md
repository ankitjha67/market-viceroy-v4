# Paper — Global Value: Building Trading Models with the 10 Year CAPE

> Faber, M.T. (2014). Global Value: Building Trading Models with the
> 10 Year CAPE. SSRN Working Paper.
> DOI: [10.2139/ssrn.2129474](https://doi.org/10.2139/ssrn.2129474).

```bibtex
@article{faber2014global,
  title   = {Global Value: Building Trading Models with the 10 Year CAPE},
  author  = {Faber, Mebane T.},
  journal = {SSRN Working Paper},
  year    = {2014},
  doi     = {10.2139/ssrn.2129474}
}
```

## Summary

Faber applies the Shiller CAPE (Cyclically Adjusted Price-to-Earnings)
ratio at the country level. Countries with low CAPE ratios (cheap) tend
to outperform countries with high CAPE ratios (expensive) over the
subsequent 5-10 years. The strategy rotates into the cheapest quartile
of country equity indices and away from the most expensive quartile,
rebalancing annually or quarterly.

The 10-year earnings smoothing in CAPE removes business-cycle noise,
making it a long-horizon value indicator.

## Phase 1 proxy

Without actual CAPE data, the strategy proxies valuation using the
trailing 10-year (2520-day) return:

- **CAPE proxy**: negative trailing 2520-day return. Low trailing
  returns imply cheapness (the market has been cheap relative to its
  long-run earnings trajectory).
- Cross-sectional ranking: assets with the lowest trailing returns
  (most "undervalued") receive the highest weight.

## Canonical parameters

| Parameter | Faber | AlphaKit default |
|---|---|---|
| Valuation metric | 10-year CAPE | 2520-day trailing return |
| Universe | Country equity indices | Any equity universe |
| Rebalance | Annual / quarterly | Monthly |

## In-sample period

Faber (2014): Global country indices, 1980-2013.
