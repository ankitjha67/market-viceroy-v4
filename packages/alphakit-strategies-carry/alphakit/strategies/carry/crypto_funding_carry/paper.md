# Paper — Crypto Funding Rate Carry

> No formal academic citation. The perpetual funding rate mechanism
> is documented in exchange specifications (Binance, Deribit, dYdX).

```bibtex
@misc{crypto_funding_carry,
  title   = {Perpetual Funding Rate Carry},
  author  = {Crypto-native},
  year    = {2020},
  note    = {No formal DOI --- exchange documentation}
}
```

## Summary

Perpetual futures use a funding rate mechanism to keep the perp
price anchored to the spot price. When the funding rate is
positive, long holders pay short holders — indicating bullish
positioning and a premium. A carry strategy collects this premium
by going short perp (or equivalently short the asset) when
funding is positive, and long when funding is negative. The
strategy harvests the persistent funding premium that arises from
speculative demand for leveraged long exposure.

## Phase 1 proxy

The StrategyProtocol provides only close prices, not actual
funding rate data. This implementation uses the fast/slow MA
spread as a funding proxy: when the fast MA is above the slow
MA by more than a threshold, funding is assumed positive (short
to collect). This is a known simplification (see ADR-001). In
production, replace with actual exchange funding rate feeds.

## Canonical parameters

| Parameter | Exchange mechanism | AlphaKit default |
|---|---|---|
| Funding signal | 8-hour funding rate | Fast/slow MA spread (proxy) |
| Fast period | N/A | 5 days |
| Slow period | N/A | 30 days |
| Threshold | N/A | 0.005 (0.5%) |
| Universe | BTC, ETH perps | BTC, ETH spot prices |

## In-sample period

Perpetual funding rate data available from 2018 onwards (BitMEX,
Binance). Strategy logic is crypto-native with no formal academic
in-sample period.
