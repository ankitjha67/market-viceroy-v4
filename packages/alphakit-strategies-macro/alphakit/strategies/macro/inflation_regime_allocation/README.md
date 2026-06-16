# inflation_regime_allocation

Inflation-regime 3-cell allocation across SPY / TLT / GLD / DBC driven
by the CPI YoY rate computed internally from CPIAUCSL (FRED).

**Family:** macro  
**DOI (primary):** [10.2469/faj.v62.n2.4080](https://doi.org/10.2469/faj.v62.n2.4080)  
**DOI (foundational):** [10.3905/jpm.2021.1.290](https://doi.org/10.3905/jpm.2021.1.290)

## Signal

The CPI YoY rate is computed internally from the lagged CPIAUCSL index:

```
cpi_yoy = cpiaucsl_lagged.pct_change(12) * 100
```

The lag is applied **before** the YoY computation to avoid lookahead bias.

## Regime allocations

| Regime | SPY | TLT | GLD | DBC |
|---|---|---|---|---|
| Low inflation (YoY < 2%) | 60% | 30% | 5% | 5% |
| Moderate inflation (2-4%) | 40% | 20% | 20% | 20% |
| High inflation (≥ 4%) | 5% | 5% | 45% | 45% |

## Key parameters

| Parameter | Default | Description |
|---|---|---|
| `low_threshold` | 2.0 | CPI YoY (%) below which regime is "low" |
| `high_threshold` | 4.0 | CPI YoY (%) at or above which regime is "high" |
| `cpi_lag_months` | 1 | Publication-lag shift applied to CPIAUCSL |

## Known failure modes

See [`known_failures.md`](known_failures.md) for documented risks:
1. Regime-boundary whipsaw (2% and 4% thresholds)
2. Publication-lag forensics (lag-before-YoY is load-bearing)
3. Gold disappointment in rate-hiking high-inflation (2022)
4. Deflation within low cell (equity-heavy in deflation)
5. DBC roll cost drag (futures-based commodity ETF)

## Universe

- **Tradable:** SPY (equity), TLT (long bonds), GLD (gold), DBC (commodities)
- **Informational:** CPIAUCSL (CPI index, zero weight)
