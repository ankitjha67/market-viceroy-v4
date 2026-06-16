# Paper — Dual Momentum Investing (Antonacci 2014)

## Citation

> Antonacci, G. (2014). *Dual Momentum Investing: An Innovative Strategy
> for Higher Returns with Lower Risk*. McGraw-Hill. ISBN 978-0071849449.
>
> Working-paper version: Antonacci, G. (2012). *Risk Premia Harvesting
> Through Dual Momentum*. SSRN 2042750.
> [https://doi.org/10.2139/ssrn.2042750](https://doi.org/10.2139/ssrn.2042750)

```bibtex
@article{antonacci2012risk,
  title   = {Risk Premia Harvesting Through Dual Momentum},
  author  = {Antonacci, Gary},
  journal = {SSRN Electronic Journal},
  year    = {2012},
  doi     = {10.2139/ssrn.2042750}
}

@book{antonacci2014dual,
  title     = {Dual Momentum Investing: An Innovative Strategy for Higher Returns with Lower Risk},
  author    = {Antonacci, Gary},
  publisher = {McGraw-Hill Education},
  year      = {2014},
  isbn      = {978-0071849449}
}
```

## Abstract (working paper)

> Dual momentum investing combines absolute with relative momentum to
> offer a powerful tool for investors to enhance returns while reducing
> risk. It is applicable across and within asset classes, and works
> consistently whether based on one-month or twelve-month look-back
> periods. This paper shows how dual momentum is an unrivaled method
> for achieving long-run outperformance both above and beyond what
> either absolute or relative momentum can provide on their own.

## Published parameters

| Parameter | Paper | AlphaKit default |
|---|---|---|
| Lookback | 12 months | 12 months |
| US equity | S&P 500 / VFINX | `"SPY"` |
| International equity | MSCI EAFE / VGTSX | `"VEU"` |
| Bonds | Barclays US Agg / VBMFX | `"AGG"` |
| Risk-free | 3-month T-bill | `"SHY"` (1–3y Treasuries) |
| Rebalance | monthly | monthly |

## In-sample period

* 1974–2013 monthly returns (paper)
* Out-of-sample: Antonacci publishes monthly returns on his blog
  (Optimal Momentum) — OOS since 2013 is broadly consistent with the
  in-sample numbers.

## Known replications

* Faber, M. (2007). "A quantitative approach to tactical asset allocation". JWM.
  (The original GTAA paper that predates but shares the spirit of GEM.)
* Antonacci's own blog posts at [optimalmomentum.com](https://www.optimalmomentum.com/).
* Zakamulin, V. (2017). *Market Timing with Moving Averages*. Palgrave.

## Implementation deviations

1. **`SHY` instead of a T-bill index.** SHY has a continuous daily
   price history via ETF wrappers; 3-month T-bill quotes live on
   FRED. The difference in total-return terms is < 10 bps/year and
   does not flip the sign of the absolute-momentum filter in any
   historical month since 2003.
2. **Distinct-symbols check in `__init__`.** The strategy requires
   four distinct symbols and will refuse to construct if any two
   overlap.
