# Paper — Do Peso Problems Explain the Returns to the Carry Trade?

> Burnside, C., Eichenbaum, M., Kleshchelski, I. & Rebelo, S. (2011).
> Do Peso Problems Explain the Returns to the Carry Trade? *Review of
> Financial Studies*, 24(3), 853-891. DOI: 10.1093/rfs/hhq138.

```bibtex
@article{burnside2011peso,
  title   = {Do Peso Problems Explain the Returns to the Carry Trade?},
  author  = {Burnside, Craig and Eichenbaum, Martin and Kleshchelski, Isaac and Rebelo, Sergio},
  journal = {Review of Financial Studies},
  volume  = {24},
  number  = {3},
  pages   = {853--891},
  year    = {2011},
  doi     = {10.1093/rfs/hhq138}
}
```

## Summary

Burnside, Eichenbaum, Kleshchelski, and Rebelo investigate whether
"peso problems" — the possibility of rare, large adverse events that
have not yet occurred in the sample — can explain the profitability
of the currency carry trade. They find that standard peso-problem
models cannot fully account for carry-trade returns, suggesting that
the forward premium puzzle reflects a genuine risk premium. The carry
trade applied to emerging-market currencies delivers higher average
returns than G10 carry but with fatter crash tails and greater
exposure to sovereign and convertibility risk.

## Phase 1 proxy

The StrategyProtocol provides only close prices, not interest rates.
This implementation uses the trailing 63-day return as a carry
proxy: EM currencies that have been appreciating are treated as
"high carry." This is a known simplification (see ADR-001). In
production, replace with actual forward discount or interest-rate
differential data.

## Canonical parameters

| Parameter | Burnside et al. | AlphaKit default |
|---|---|---|
| Carry signal | Interest-rate differential | Trailing 63-day return (proxy) |
| Long basket | Top 3 | 3 |
| Short basket | Bottom 3 | 3 |
| Universe | EM currencies | 6 EM pairs vs USD |

## In-sample period

Burnside et al. tested on developed and EM currencies, 1976-2008.
