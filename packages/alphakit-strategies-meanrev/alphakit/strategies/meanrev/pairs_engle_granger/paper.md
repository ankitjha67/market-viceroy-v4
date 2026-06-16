# Paper — Co-Integration and Error Correction

> Engle, R.F. & Granger, C.W.J. (1987). Co-Integration and Error
> Correction: Representation, Estimation, and Testing. *Econometrica*,
> 55(2), 251-276. DOI: 10.2307/1913236.

```bibtex
@article{engle1987cointegration,
  title     = {Co-Integration and Error Correction: Representation, Estimation, and Testing},
  author    = {Engle, Robert F. and Granger, Clive W. J.},
  journal   = {Econometrica},
  volume    = {55},
  number    = {2},
  pages     = {251--276},
  year      = {1987},
  doi       = {10.2307/1913236}
}
```

## Summary

Engle and Granger introduce the concept of cointegration: two or more
non-stationary time series that share a common stochastic trend such
that a linear combination of them is stationary. The two-step procedure
first estimates the cointegrating regression via OLS, then tests the
residual for stationarity (ADF test on residuals).

For pairs trading, if two asset prices are cointegrated, the spread
(price_A - beta * price_B) is stationary and mean-reverting. This
implementation uses a rolling OLS to estimate the hedge ratio (beta)
and trades when the Z-score of the spread exceeds a threshold.

## Canonical parameters

| Parameter        | Paper            | AlphaKit default |
|------------------|------------------|------------------|
| Formation period | 12 months (252d) | 252              |
| Z-score lookback | 20 days          | 20               |
| Entry threshold  | 2.0 sigma        | 2.0              |

## In-sample period

Theoretical paper; empirical examples use post-war macroeconomic
data. Widely applied to equities, FX, and fixed income.
