# Known failure modes — crypto_funding_carry

## 1. Persistent funding regimes

Crypto funding rates can remain persistently positive (or negative)
for weeks during strong trends. The strategy assumes mean-reversion
of the funding rate, but in a sustained bull market, continuously
shorting to collect positive funding produces large directional
losses that dwarf the funding income.

## 2. Proxy limitation

The fast/slow MA spread is a crude approximation of actual funding
rates. It misses intraday funding dynamics, exchange-specific
differences, and can produce signals that diverge from actual
funding direction — especially during choppy, range-bound markets.

## 3. Exchange risk

Real funding carry requires holding positions on centralized
exchanges. Exchange failures (e.g., FTX collapse), API outages,
and liquidation cascades introduce risks that are not captured
in a price-only backtest.

## 4. 24/7 markets

Crypto markets trade continuously, but this implementation uses
business-day frequency. Weekend and overnight moves can cause
significant gaps between the signal generation time and actual
execution, leading to slippage and stale signals.
