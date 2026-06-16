# Paper — Variance Risk Premia

> Carr, P. & Wu, L. (2009). Variance Risk Premia. *Review of
> Financial Studies*, 22(3), 1311-1341. DOI: 10.1093/rfs/hhn038.

```bibtex
@article{carr2009variance,
  title   = {Variance Risk Premia},
  author  = {Carr, Peter and Wu, Liuren},
  journal = {Review of Financial Studies},
  volume  = {22},
  number  = {3},
  pages   = {1311--1341},
  year    = {2009},
  doi     = {10.1093/rfs/hhn038}
}
```

## Summary

Carr and Wu document the variance risk premium — the difference
between risk-neutral (implied) and physical (realized) variance.
Across equity indices and individual stocks, implied variance
systematically exceeds realized variance, generating a negative
variance risk premium for variance buyers. Selling variance
(short vol) earns a carry-like premium most of the time, with
occasional large drawdowns during volatility spikes.

## Phase 1 proxy

The StrategyProtocol provides only close prices, not implied
volatility or VIX data. This implementation estimates the VRP
by comparing fast (5-day) vs slow (20-day) realized volatility.
When fast vol is below slow vol, the VRP proxy is positive
(contango regime); the strategy goes long to capture the premium.
This is a known simplification (see ADR-001). In production,
replace with actual implied vs realized vol spread.

## Canonical parameters

| Parameter | Carr & Wu | AlphaKit default |
|---|---|---|
| VRP signal | Implied − realized variance | Fast/slow realized vol spread (proxy) |
| Fast window | N/A | 5 days |
| Slow window | N/A | 20 days |
| Universe | S&P 500, individual stocks | Equity and futures |

## In-sample period

Carr & Wu tested on S&P 500 and 35 individual stocks, 1996-2003.
