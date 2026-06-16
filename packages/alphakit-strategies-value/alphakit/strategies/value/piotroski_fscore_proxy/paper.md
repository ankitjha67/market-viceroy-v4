# Paper — Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers

> Piotroski, J.D. (2000). Value Investing: The Use of Historical
> Financial Statement Information to Separate Winners from Losers.
> *Journal of Accounting Research*, 38(Supplement), 1-41.
> DOI: [10.2307/2672906](https://doi.org/10.2307/2672906).

```bibtex
@article{piotroski2000value,
  title   = {Value Investing: The Use of Historical Financial Statement
             Information to Separate Winners from Losers},
  author  = {Piotroski, Joseph D.},
  journal = {Journal of Accounting Research},
  volume  = {38},
  pages   = {1--41},
  year    = {2000},
  doi     = {10.2307/2672906}
}
```

## Summary

Piotroski constructs a 9-point composite score (F-Score) from
accounting signals to distinguish winners from losers within the
universe of high book-to-market (value) stocks. The 9 binary signals
cover profitability (ROA, cash flow from operations, change in ROA,
accruals), leverage/liquidity (change in leverage, change in current
ratio, equity issuance), and operating efficiency (change in gross
margin, change in asset turnover). High F-Score stocks (7-9)
significantly outperform low F-Score stocks (0-2).

## SEVERE DEVIATION — price-based proxy (ADR-002)

**This implementation is NOT the real Piotroski F-Score.**

The `_proxy` suffix applies per ADR-002. All 9 accounting signals are
replaced by price-derived indicators:

| # | Original (accounting) | Proxy (price-based) |
|---|---|---|
| 1 | Positive ROA | Positive 12-month return |
| 2 | Positive CFO | Positive 1-month return |
| 3 | Improving ROA | 12m return > 6m return |
| 4 | Low leverage | Low trailing volatility |
| 5 | Improving leverage | Decreasing volatility (6m < 12m) |
| 6 | Solvency (current ratio) | Price above 200-day SMA |
| 7 | No equity dilution | Positive 3-month return |
| 8 | Improving gross margin | 3m return > cross-sectional average |
| 9 | Improving asset turnover | Low max drawdown (12m) |

The proxy signals are primarily momentum and volatility indicators.
They do **not** measure accounting quality, profitability, or balance
sheet health. The canonical slug `piotroski_fscore` is reserved for
Phase 4 when real accounting data is available.

## Canonical parameters

| Parameter | Piotroski | AlphaKit default |
|---|---|---|
| Signals | 9 accounting | 9 price-based |
| Universe | High B/M stocks | Any equity universe |
| Rebalance | Annual | Monthly |

## In-sample period

Piotroski (2000): US high book-to-market stocks, 1976-1996.
