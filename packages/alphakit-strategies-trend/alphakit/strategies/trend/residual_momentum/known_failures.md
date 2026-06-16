# Known failure modes — residual_momentum

## 1. Single-factor market model under-hedges during factor rotations

The AlphaKit Phase 1 implementation hedges only the cross-sectional mean
(β=1 assumed for every stock). During regimes where size or value
factors dominate (e.g. the Jan 2021 small-cap rally, the 2023 small-cap
crash), the residual signal still contains meaningful SMB exposure, so
the drawdown can be larger than the paper's full FF3 variant would
produce.

Mitigation: use the Phase 4 `residual_momentum_ff3` variant when it
ships.

## 2. Momentum crashes (same as xs_momentum_jt)

The 2009 momentum crash hit residual-momentum strategies only slightly
less hard than the vanilla variant — the short-side blowup happens
regardless of whether the signal was total or residual.

## 3. Small universes degrade the market proxy

With 3–5 assets in the universe, the equal-weighted mean is dominated
by one or two names, so "residual = asset − market" is essentially
"asset − other asset" on the tiny universe. The economic signal
degrades. A universe of 10+ is preferable.

## 4. Equity-only

Same as xs_momentum_jt — the factor hedging logic assumes equity-like
cross-sectional structure and does not transfer to futures or FX.
