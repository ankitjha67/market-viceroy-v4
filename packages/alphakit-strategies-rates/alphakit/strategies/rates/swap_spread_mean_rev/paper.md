# Paper — Swap-Treasury Spread Mean-Reversion (Duarte/Longstaff/Yu 2007)

## Citations

**Initial inspiration:** Liu, J., Longstaff, F. A. & Mandell, R. E.
(2006). **The market price of risk in interest rate swaps: The roles
of default and liquidity risks.** *Journal of Business*, 79(5),
2337–2359.
[https://doi.org/10.1086/505250](https://doi.org/10.1086/505250)

**Primary methodology:** Duarte, J., Longstaff, F. A. & Yu, F.
(2007). **Risk and return in fixed-income arbitrage: nickels in
front of a steamroller?** *Review of Financial Studies*, 20(3),
769–811.
[https://doi.org/10.1093/rfs/hhl026](https://doi.org/10.1093/rfs/hhl026)

BibTeX entries: `liuLongstaffMandell2006swap` (foundational) and
`duarteLongstaffYu2007arbitrage` (primary) in `docs/papers/phase-2.bib`.

## Why two papers

Liu/Longstaff/Mandell (2006) provides the *risk-factor* result: the
swap-Treasury spread is a stationary, mean-reverting process driven
by default-risk and liquidity-premium components.

Duarte/Longstaff/Yu (2007) provides the *expected-return* result:
trading deviations of swap-Treasury basis from its long-run mean
earns positive risk-adjusted returns net of transaction costs but
with material tail risk during stress (LTCM 1998, GFC 2008-09).
The paper title — "nickels in front of a steamroller" — is the
canonical risk warning.

The synthesis is the explicit z-score-and-trade rule implemented
here.

## Differentiation from sibling rates strategies

* `curve_steepener_2s10s` / `curve_flattener_2s10s` /
  `curve_butterfly_2s5s10s` — trade the *yield-curve slope* on
  Treasuries alone. Different signal type entirely.
* `swap_spread_mean_rev` (this strategy) trades the *swap-Treasury
  basis*, driven by funding costs, liquidity, and balance-sheet
  constraints rather than expected rate path.

The two signals are largely orthogonal in normal regimes (expected
ρ ≈ 0.1-0.2). They overlap during stress regimes when both the
slope and the swap spread move sharply (e.g. 2008 Q4: both flat-
inverted curve and elevated swap spread).

## Algorithm

For each daily bar:

1. ``log_spread = log(P_treasury) − log(P_swap)``.
2. ``z = (log_spread − rolling_mean) / rolling_std`` over a 252-day
   trailing window.
3. **Mean-reversion entry** (both directions):

   * ``z > +entry_threshold`` → swap rate is unusually rich vs
     Treasury → expect spread to tighten → SHORT Treasury, LONG
     swap.
   * ``z < −entry_threshold`` → swap rate is unusually cheap vs
     Treasury → expect spread to widen → LONG Treasury, SHORT
     swap.

4. **Exit** when ``|z| < exit_threshold``.

| Parameter | Default | Notes |
|---|---|---|
| `zscore_window` | `252` | ≈ 1 year |
| `entry_threshold` | `1.0` σ | enter on ±1σ extreme |
| `exit_threshold` | `0.25` σ | hysteresis avoids whipsaw |

Position sizing is equal dollar weight on each leg (±1.0 / ∓1.0).
The duration mismatch between IEF (Treasury proxy) and a 10Y swap
is small if the swap is matched-maturity, but larger if the swap
is shorter or longer; documented as a known failure.

## In-sample period (Duarte/Longstaff/Yu 2007)

* Data: 1988–2004 monthly, US Treasury and swap rates
* Sharpe of 0.6-0.9 on the swap-spread arbitrage net of estimated
  transaction costs
* Documented tail risk: LTCM 1998 produced a 30% drawdown on the
  basis-arbitrage portfolio over a 6-week window
* The "steamroller" analogy: most months earn small positive
  returns; a few stress months erase them

## Implementation deviations from Duarte/Longstaff/Yu

1. **Price-space proxy** for the swap-Treasury spread instead of
   explicit yield-spread computation. The proxy is monotone in the
   yield spread but the absolute units differ.
2. **Equal-dollar weights** rather than precise duration-matched
   DV01 weights. Real-feed Session 2H benchmark with explicit
   yield data should compute matched DV01 sizes.
3. **No bid-ask, repo-funding, or short-borrow model.** Duarte
   et al. estimate ~5-10 bps round-trip on the basis trade; the
   bridge applies a flat ``commission_bps`` parameter that doesn't
   capture the asymmetric cost structure (Treasury repo is liquid,
   swap collateral posting is more expensive).
4. **No data feed for liquid swap-rate proxy.** US-listed swap-
   tracking ETFs are illiquid or absent; real-feed Session 2H
   benchmark must construct the swap-rate series from FRED's ICE
   swap rate (`USDOIS3MD156N`-style) and the duration approximation.

## Known replications and follow-ups

* **Krishnamurthy (2002)** — "The Bond/Old-Bond Spread", JFE.
  Related liquidity-driven basis strategy on the on-the-run /
  off-the-run Treasury spread.
* **Brunnermeier & Pedersen (2009)** — "Market Liquidity and
  Funding Liquidity", RFS. Theoretical framework explaining when
  swap-spread arbitrage breaks down (the "steamroller" tail
  events).
