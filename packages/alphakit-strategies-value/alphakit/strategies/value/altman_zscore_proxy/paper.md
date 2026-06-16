# Paper — Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy

> Altman, E.I. (1968). Financial Ratios, Discriminant Analysis and
> the Prediction of Corporate Bankruptcy. *Journal of Finance*, 23(4),
> 589-609. DOI: [10.1111/j.1540-6261.1968.tb00843.x](https://doi.org/10.1111/j.1540-6261.1968.tb00843.x).

```bibtex
@article{altman1968financial,
  title   = {Financial Ratios, Discriminant Analysis and the Prediction
             of Corporate Bankruptcy},
  author  = {Altman, Edward I.},
  journal = {Journal of Finance},
  volume  = {23},
  number  = {4},
  pages   = {589--609},
  year    = {1968},
  doi     = {10.1111/j.1540-6261.1968.tb00843.x}
}
```

## Summary

The Altman Z-Score is a linear discriminant function of five
accounting ratios that predicts corporate bankruptcy:

  Z = 1.2X1 + 1.4X2 + 3.3X3 + 0.6X4 + 1.0X5

where X1 = working capital / total assets, X2 = retained earnings /
total assets, X3 = EBIT / total assets, X4 = market value of equity /
book value of total liabilities, X5 = sales / total assets.

Scores above 2.99 indicate safety; below 1.81 indicate distress.

## SEVERE DEVIATION — price-based proxy (ADR-002)

**This implementation is NOT the real Altman Z-Score.**

The `_proxy` suffix applies per ADR-002. All 5 accounting ratios are
replaced by price-derived distress indicators:

| # | Original (accounting) | Proxy (price-based) |
|---|---|---|
| X1 | Working capital / total assets | Negative 12-month drawdown (less drawdown = healthier) |
| X2 | Retained earnings / total assets | Low trailing volatility (lower vol = healthier) |
| X3 | EBIT / total assets | Price / 200-day SMA ratio (above SMA = healthier) |
| X4 | Market value equity / book liabilities | 12-month return (higher = healthier) |
| X5 | Sales / total assets | (omitted — 4 proxy signals used) |

The proxy measures price-based "health" (low drawdown, low volatility,
positive trend, positive momentum). It does **not** detect actual
balance sheet deterioration, insolvency risk, or accounting fraud.
The canonical slug `altman_zscore` is reserved for Phase 4 when real
accounting data is available.

## Canonical parameters

| Parameter | Altman | AlphaKit default |
|---|---|---|
| Inputs | 5 accounting ratios | 4 price-based signals |
| Scoring | Linear discriminant | Cross-sectional rank sum |
| Rebalance | N/A (diagnostic) | Monthly |

## In-sample period

Altman (1968): US manufacturing firms, 1946-1965.
