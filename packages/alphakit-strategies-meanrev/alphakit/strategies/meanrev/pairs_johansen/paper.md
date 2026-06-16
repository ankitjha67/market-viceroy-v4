# Paper — Estimation and Hypothesis Testing of Cointegration Vectors

> Johansen, S. (1991). Estimation and Hypothesis Testing of
> Cointegration Vectors in Gaussian Vector Autoregressive Models.
> *Econometrica*, 59(6), 1551-1580. DOI: 10.2307/2938278.

```bibtex
@article{johansen1991estimation,
  title   = {Estimation and Hypothesis Testing of Cointegration Vectors in Gaussian Vector Autoregressive Models},
  author  = {Johansen, S{\o}ren},
  journal = {Econometrica},
  volume  = {59},
  number  = {6},
  pages   = {1551--1580},
  year    = {1991},
  doi     = {10.2307/2938278}
}
```

## Summary

Johansen extends the Engle-Granger two-step procedure to a multi-asset
setting via a VECM (Vector Error Correction Model). The method finds all
cointegrating vectors simultaneously via eigendecomposition, making it
suitable for portfolios of 3+ assets.

## Parameters

| Parameter | Default |
|---|---|
| Formation period | 252 days |
| Z-score lookback | 20 |
| Entry threshold | ±2σ |
