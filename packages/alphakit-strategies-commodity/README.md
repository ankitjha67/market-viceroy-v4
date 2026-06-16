# alphakit-strategies-commodity

Commodity strategies for [AlphaKit](https://github.com/ankitjha67/alphakit).

Phase 2 target: 10 strategies on energy futures (WTI / Brent / NG),
metals (gold / silver / copper / platinum), agricultural commodities
(corn / soybeans / wheat / soybean meal & oil), CFTC speculator
positioning, and cross-commodity carry / momentum. Real-feed
benchmarks use the `yfinance-futures`, `eia`, and `cftc-cot` adapters
from `alphakit-data` (all wired in Phase 2 Session 2B).

The Session 2E shipping count is 10, not the originally-planned 15:
`energy_weather_premium`, `henry_hub_ttf_spread`, `inventory_surprise`,
`calendar_spread_corn`, and `coffee_weather_asymmetry` were dropped
under the Phase 2 honesty-check (no citable systematic-strategy
papers, missing data feeds for non-US markets, and folk-wisdom
trades without academic anchors). See `docs/phase-2-amendments.md`
for the full audit trail.
