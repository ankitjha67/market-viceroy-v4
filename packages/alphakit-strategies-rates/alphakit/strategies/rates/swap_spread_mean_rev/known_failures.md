# Known failure modes — swap_spread_mean_rev

> Duarte/Longstaff/Yu (2007) call this strategy "nickels in front
> of a steamroller" — small positive returns most of the time,
> large losses during funding crises. The 1998 LTCM crisis and
> 2008-09 GFC are both periods where the swap-spread mean-reversion
> assumption broke down.

Mean-reversion on the swap-Treasury basis. Will lose money in the
regimes below.

## 1. Funding stress (LTCM 1998, GFC 2008 Q4)

When dealer balance sheets contract, funding costs spike, and
swap-Treasury basis can move sharply *away* from its long-run
mean for weeks or months. The strategy enters the position
expecting reversion; the reversion arrives only after a 20-30%
drawdown.

This is the canonical "steamroller" failure. Mitigation:
* Pair the strategy with a funding-stress filter (e.g. exit when
  TED spread or LIBOR-OIS exceeds a threshold) — Phase 3
  candidate.
* Size the strategy small relative to the portfolio so a 30%
  drawdown on this sleeve is survivable.

## 2. Negative-swap-spread regime (post-2010)

After 2010, US swap spreads turned negative for the first time —
swap rates traded *below* Treasury yields, contradicting the
default-and-liquidity decomposition that says swaps should always
be at a premium. The "long-run mean" of the swap spread shifted
from +20-50 bps (pre-2010) to roughly zero (post-2010).

A 252-day rolling z-score adapts to the new regime within a year,
but during the 2010-2011 transition the strategy whipsawed
repeatedly as the regime change wasn't yet captured by the
trailing window.

Real-feed Session 2H benchmarks should use a longer rolling window
(e.g. 504-day = 2 years) for stability across regime changes,
or pair with a level-anchored signal that tracks the swap-spread
mean explicitly.

## 3. Imperfect Treasury / swap leg matching

The strategy's `prices` interface accepts whatever pair of bond-
price proxies is passed. Default config suggests `IEF` (7-10Y
Treasury) and `IRS_10Y` (10Y interest rate swap proxy). In reality:

* `IEF` has effective duration ≈ 8 years, but the 10Y swap
  has effective duration ≈ 8.5 years (slightly longer).
* `IRS_10Y` is not a real ticker — there is no liquid US-listed
  10Y swap ETF. Real-feed Session 2H benchmarks must construct
  the swap-rate proxy from FRED's ICE swap rate and the duration
  approximation.

The duration mismatch is small (~6%) but means parallel-shift
exposure leaks into the basis P&L.

## 4. Repo / funding cost asymmetry

The basis trade requires:

* Long Treasury via cash market (or via repo, ~zero cost).
* Short swap via paying fixed (no upfront cost but requires
  posting variation margin, costs ~10-20 bps annualised in
  funding).

The bridge's flat ``commission_bps`` parameter doesn't capture
this asymmetry. Documented turn-around cost in DLY 2007 is ~5-10
bps round-trip; in practice during funding stress (2008-09,
2020 March) round-trip costs spike to 20-50 bps.

## 5. Cluster correlation with sibling strategies

* `curve_steepener_2s10s`, `curve_flattener_2s10s`,
  `curve_butterfly_2s5s10s` — slope/curvature trades. Largely
  orthogonal to swap-spread mean-reversion in normal regimes
  (expected ρ ≈ 0.1-0.2). Overlap during stress regimes when both
  slope and basis move sharply.
* `bond_carry_rolldown` — duration overlay on slope. Expected
  ρ ≈ 0.1-0.3.

None cross 0.95.

## 6. No swap-rate data feed in scope for Phase 2

The `IRS_10Y` placeholder in the default config is not a real data
source. Real-feed Session 2H benchmark requires:

* FRED `USDOIS3MD156N` for OIS rate
* FRED ICE swap rate series for fixed-leg
* Duration approximation to convert to a price-equivalent series

This is a non-trivial data-engineering task documented as a
Session 2H prerequisite.

## Regime performance (reference, gross of fees, swap-spread mean-reversion)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-LTCM (1995-1997) | 1995-01 – 1997-12 | ~1.0 | −3% |
| LTCM 1998 | 1998-08 – 1998-12 | ~−2.0 | −22% |
| Post-LTCM recovery (1999-2007) | 1999-2007 | ~0.7 | −5% |
| GFC (2008 Q4) | 2008-09 – 2008-12 | ~−2.5 | −28% |
| QE-era stable (2010-2019) | 2010-2019 | ~0.4 | −7% |
| 2020 March COVID dislocation | 2020-03 – 2020-04 | ~−1.5 | −18% |
| 2022 rate shock | 2022-2022 | ~0.2 | −6% |

(Reference ranges from Duarte/Longstaff/Yu (2007) Table 4 plus
practitioner tail-risk reports; the in-repo benchmark is
authoritative for this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
