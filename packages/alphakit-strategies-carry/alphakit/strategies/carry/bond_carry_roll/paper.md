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

Koijen, Moskowitz, Pedersen, and Vrugt define bond carry as the
yield plus the roll-down return — the price appreciation a bond
earns as it ages along a positively sloped yield curve. The strategy
ranks sovereign bond markets by carry and constructs a dollar-neutral
portfolio: long high-carry (high-yield, steep-curve) markets, short
low-carry markets. KMPV show that bond carry delivers significant
risk-adjusted returns and is distinct from standard duration and
term-structure factors.

## Phase 1 proxy

The StrategyProtocol provides only close prices, not yield-curve
data. This implementation uses the trailing 63-day return as a
carry proxy for sovereign bond futures. This is a known
simplification (see ADR-001). The proxy does not capture actual
bond yield or roll-down; it conflates carry with momentum. In
production, replace with actual yield and roll-down estimates
from yield-curve data.

## Canonical parameters

| Parameter | KMPV (2018) | AlphaKit default |
|---|---|---|
| Carry signal | Yield + roll-down | Trailing 63-day return (proxy) |
| Lookback | N/A (point-in-time yield) | 63 days |
| Portfolio | Dollar-neutral | Dollar-neutral (rank-demean) |
| Universe | Sovereign bonds | 6 sovereign 10Y futures |

## In-sample period

KMPV tested on sovereign bonds, 1972-2014.
