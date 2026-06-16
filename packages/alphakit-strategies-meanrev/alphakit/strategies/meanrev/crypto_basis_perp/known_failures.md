# Known failure modes — crypto_basis_perp

## 1. Persistent premium regimes

During strong bull markets, the perp basis can stay positive for
weeks or months. The strategy will be short throughout, accumulating
losses on both price and funding.

## 2. Basis proxy limitation

Without actual perp/spot data, the fast/slow MA spread is an
imperfect proxy. The true basis depends on exchange-specific funding
mechanisms and can diverge from the MA-based approximation.

## 3. Exchange risk

In practice, basis trades require holding positions on centralized
exchanges. Exchange failures (FTX), withdrawals, or liquidation
cascades can wipe out positions regardless of the signal's quality.

## 4. 24/7 markets

Crypto trades continuously. The daily rebalance frequency may miss
intraday basis spikes and reversals that occur outside the daily
close snapshot.
