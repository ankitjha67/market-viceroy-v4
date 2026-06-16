# Paper — A Century of Evidence on Trend-Following Investing

## Citation

> Hurst, B., Ooi, Y. H. & Pedersen, L. H. (2017).
> **A Century of Evidence on Trend-Following Investing.**
> *The Journal of Portfolio Management*, 44(1), 15–29.
> AQR Capital Management working paper, SSRN 2993026.
> [https://doi.org/10.2139/ssrn.2993026](https://doi.org/10.2139/ssrn.2993026)

BibTeX:

```bibtex
@article{hurst2017century,
  title   = {A Century of Evidence on Trend-Following Investing},
  author  = {Hurst, Brian and Ooi, Yao Hua and Pedersen, Lasse Heje},
  journal = {The Journal of Portfolio Management},
  volume  = {44},
  number  = {1},
  pages   = {15--29},
  year    = {2017},
  doi     = {10.2139/ssrn.2993026}
}
```

## Abstract

> We study the performance of trend-following investing across global
> markets since 1880, extending the existing evidence by more than 100
> years using a novel data set. We find that in each decade since
> 1880, time-series momentum has delivered positive average returns
> with low correlations to traditional asset classes. Further, time-
> series momentum has performed well in 8 of 10 of the largest crises
> over the past 110 years, providing positive returns in 68% of
> bear-market months and negative returns in only 32% of them.
> Lastly, we find that time-series momentum has performed well across
> different macroeconomic environments, including recessions and
> booms, war and peacetime, high- and low-interest rate regimes, and
> high- and low-volatility periods.

## Published parameters (vs. AlphaKit defaults)

| Parameter | Paper | AlphaKit default | Notes |
|---|---|---|---|
| Lookback | 1 / 3 / 12 months, averaged | 12 months | we ship the single-lookback variant as the reference |
| Skip | 0 months | 1 month | aligned to MOP 2012 for comparability |
| Signal | hyperbolic tangent of normalised return | ``tanh(z_score)`` | identical |
| Vol target (per asset) | 40% annualised | 10% | rescaled for a 6-asset ETF universe |
| Vol estimator | 3-year EWMA | 63-day rolling σ | deterministic in CI |
| Rebalance | monthly | monthly | same |

## In-sample period

* 1880 – 2016, global multi-asset futures (the paper's key contribution
  is the 137-year panel).

## Known replications

* Hurst, Ooi & Pedersen (2013). "Demystifying Managed Futures". JIM.
* Levine, A. & Pedersen, L. H. (2016). "Which Trend is Your Friend?". FAJ.
* Baltas, N. & Kosowski, R. (2013). "Momentum Strategies in Futures Markets
  and Trend-Following Funds". SSRN 1968996.

## Implementation deviations

1. **Single lookback (12m) instead of the paper's 1/3/12 average.** The
   AlphaKit Phase 1 target list includes `tsmom_volscaled` as the
   canonical continuous-signal TSMOM; Phase 4 will add
   `tsmom_multi_horizon` as the full 1/3/12 average.
2. **63-day rolling stdev** instead of EWMA for reproducibility.
3. **Rescaled vol target** — see note in `config.yaml`.
