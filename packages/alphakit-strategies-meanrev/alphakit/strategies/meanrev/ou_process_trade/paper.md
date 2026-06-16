# Paper — Statistical Arbitrage in the US Equities Market

> Avellaneda, M. & Lee, J.-H. (2010). Statistical Arbitrage in the
> US Equities Market. *Quantitative Finance*, 10(7), 761-782.
> DOI: 10.1080/14697680902743953.

```bibtex
@article{avellaneda2010statistical,
  title   = {Statistical Arbitrage in the US Equities Market},
  author  = {Avellaneda, Marco and Lee, Jeong-Hyun},
  journal = {Quantitative Finance},
  volume  = {10},
  number  = {7},
  pages   = {761--782},
  year    = {2010},
  doi     = {10.1080/14697680902743953}
}
```

## Summary

Avellaneda and Lee model stock returns as an Ornstein-Uhlenbeck (OU)
process — a continuous-time mean-reverting stochastic process with
three parameters: the long-run mean (mu), the speed of mean reversion
(theta), and the volatility (sigma). The half-life of mean reversion
(ln(2)/theta) determines how quickly prices revert to the mean.

The strategy calibrates OU parameters on a rolling window, computes
the Z-score of the current deviation from the OU mean, and sizes
positions inversely proportional to the half-life: faster mean
reversion → larger position.

## Key parameters

| Parameter | Paper | AlphaKit default |
|---|---|---|
| Calibration window | 60 days | 60 |
| Max half-life filter | N/A | 120 days |

## In-sample period

Avellaneda & Lee tested on US equities 1997-2007.
