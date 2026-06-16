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

Avellaneda and Lee decompose stock returns using PCA into systematic
(factor) and idiosyncratic (residual) components. The residuals are
modeled as OU processes. When the cumulative residual deviates
significantly from zero, the strategy trades its mean reversion.

## Parameters

| Parameter | Paper | AlphaKit default |
|---|---|---|
| Number of factors | 15 | 15 |
| Formation period | 252 | 252 |
| Z-score lookback | 20 | 20 |
| Entry threshold | ±2σ | 2.0 |
| Residual decay | 0.95 | 0.95 |
