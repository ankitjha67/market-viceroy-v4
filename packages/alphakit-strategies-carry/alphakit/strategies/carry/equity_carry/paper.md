# Paper — Carry

> Koijen, R.S.J., Moskowitz, T.J., Pedersen, L.H. & Vrugt, E.B.
> (2018). Carry. *Journal of Financial Economics*, 127(2), 197-225.
> DOI: 10.1016/j.jfineco.2017.11.002.

```bibtex
@article{koijen2018carry,
  title   = {Carry},
  author  = {Koijen, Ralph S.J. and Moskowitz, Tobias J. and Pedersen, Lasse Heje and Vrugt, Evert B.},
  journal = {Journal of Financial Economics},
  volume  = {127},
  number  = {2},
  pages   = {197--225},
  year    = {2018},
  doi     = {10.1016/j.jfineco.2017.11.002}
}
```

## Summary

Koijen, Moskowitz, Pedersen, and Vrugt propose a unified definition
of "carry" as the expected return on an asset assuming its price
stays constant. For equities, carry equals the dividend yield plus
expected buyback yield. They show that a cross-sectional carry
strategy — long high-carry, short low-carry — earns significant
risk-adjusted returns across asset classes. In equities specifically,
the carry factor is distinct from value and momentum, though it
shares some overlap with dividend yield strategies.

## Phase 1 proxy

The StrategyProtocol provides only close prices, not dividend or
buyback data. This implementation uses the trailing 252-day return
as a carry proxy and ranks assets cross-sectionally. The portfolio
is dollar-neutral. This is a known simplification (see ADR-001).
The proxy conflates carry with momentum. In production, replace
with actual dividend yield and buyback yield data.

## Canonical parameters

| Parameter | KMPV (2018) | AlphaKit default |
|---|---|---|
| Carry signal | Dividend + buyback yield | Trailing 252-day return (proxy) |
| Lookback | N/A (point-in-time yield) | 252 days |
| Portfolio | Dollar-neutral | Dollar-neutral (rank-demean) |
| Universe | Global equities | 6 ETFs (SPY, EFA, EEM, AGG, GLD, DBC) |

## In-sample period

KMPV tested on global equities, 1972-2014.
