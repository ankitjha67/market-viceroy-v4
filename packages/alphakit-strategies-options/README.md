# alphakit-strategies-options

Options strategies for [AlphaKit](https://github.com/ankitjha67/alphakit).

Phase 2 target: 15 strategies on systematic short-volatility writes
(covered call, cash-secured put, BXM replication, BXMP overlay), short-
volatility multi-leg structures (iron condor, short strangle, weekly
short-vol), Greeks-dependent positions (delta-hedged straddle, daily
gamma scalping), variance-risk-premium harvesting, term-structure
trades (calendar spread), substrate-caveat skew trades (put-skew
premium, skew reversal), and VIX trades (term-structure roll on real
`^VIX`/`VIX=F`, 3-month constant-maturity basis on `^VIX`/`^VIX3M`).
Option chains are sourced from the synthetic-options adapter (ADR-005)
which prices Black-Scholes quotes from realized-vol-derived implied
volatility — the Phase 2 default options feed in lieu of a paid
Polygon integration. VIX strategies source from `yfinance` (CBOE
indices via `^`-prefix passthrough) and `yfinance-futures` (`VIX=F`).

The Session 2F shipping count is 15, not the originally-planned 20:
`diagonal_spread`, `pin_risk_capture`, `earnings_vol_crush`,
`ratio_spread_put`, and `dispersion_trade_proxy` were dropped under
the Phase 2 honesty-check (folklore mechanics without peer-reviewed
systematic-strategy citations, plus substrate mismatches the synthetic
chain cannot represent — pinning microstructure, earnings-vol term
structure, and individual-stock chains). Three plan slugs were
reframed: `wheel_strategy → bxmp_overlay`,
`vix_front_back_spread → vix_3m_basis`,
`weekly_theta_harvest → weekly_short_volatility`. See
`docs/phase-2-amendments.md` for the full audit trail.
