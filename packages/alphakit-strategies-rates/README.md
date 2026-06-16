# alphakit-strategies-rates

Rates strategies for [AlphaKit](https://github.com/ankitjha67/alphakit).

Phase 2 target: 13 strategies on US Treasury yield curves, breakeven
inflation, real yields, sovereign cross-section carry, IG credit spreads,
swap-Treasury spreads, and global inflation differentials. Real-feed
benchmarks use the FRED adapter from `alphakit-data`.

The Session 2D shipping count is 13, not the originally-planned 15:
`fed_funds_surprise` and `fra_ois_spread` were dropped under the Phase 2
honesty-check (no fed-funds-futures data on FRED; FRA-OIS is a stress
indicator, not a systematic strategy with a citable rule). See
`docs/phase-2-amendments.md` for the full audit trail.
