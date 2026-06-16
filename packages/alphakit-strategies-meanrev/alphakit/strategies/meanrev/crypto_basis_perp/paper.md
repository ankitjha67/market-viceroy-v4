# Crypto — Perpetual-Spot Basis Mean Reversion

> No formal academic citation. The perp-spot basis (funding rate
> arbitrage) is a well-documented crypto-native phenomenon documented
> in exchange whitepapers and practitioner literature.

## Summary

Perpetual futures in crypto markets trade with a funding rate mechanism
that periodically transfers payments between longs and shorts based on
the basis (perp price − spot price). When the basis is positive (perp
at premium), longs pay shorts; when negative, shorts pay longs.

The basis tends to mean-revert because extreme premiums attract
arbitrageurs who sell the perp and buy spot (or vice versa). This
strategy fades extreme basis levels by going long when the basis is
unusually negative and short when unusually positive.

## Implementation note

Since the StrategyProtocol provides only close prices (no separate
perp and spot feeds), this implementation uses the fast/slow MA spread
as a basis proxy. In production, you would supply perp and spot as
separate columns and compute the actual basis.

## Parameters

| Parameter | Default |
|---|---|
| Fast MA period | 5 |
| Slow MA period | 30 |
| Z-score lookback | 20 |
| Entry threshold | ±2σ |
