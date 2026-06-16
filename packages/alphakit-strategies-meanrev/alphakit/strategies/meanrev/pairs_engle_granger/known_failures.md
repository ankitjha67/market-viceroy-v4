# Known failure modes — pairs_engle_granger

## 1. Spurious cointegration

Two trending series may appear cointegrated by chance during the
formation period, especially with short samples. The ADF test has
limited power against near-unit-root alternatives, and the rolling
OLS approach used here does not explicitly test for cointegration
at each step.

## 2. Unstable hedge ratio

The hedge ratio (beta) estimated via OLS can change significantly
over time. A beta that was stable during the formation period may
drift during the trading period, causing the spread to diverge from
its historical mean.

## 3. Regime changes

Cointegration relationships can break down during regime changes
such as monetary policy shifts, sector rotations, or structural
economic changes. The strategy assumes the long-run equilibrium
persists, which may not hold across regimes.

## 4. Only 2-asset at a time

The Engle-Granger procedure is inherently a bivariate method. When
applied to a universe of N assets, the strategy enumerates all
O(N^2) pairs independently, which misses multi-asset cointegration
relationships and can lead to overlapping, correlated positions.
