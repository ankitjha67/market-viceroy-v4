# Paper — Real-Yield Momentum (Asness §V on TIPS, after Pflueger/Viceira 2011)

## Citations

**Initial inspiration:** Pflueger, C. E. & Viceira, L. M. (2011).
**An empirical decomposition of risk and liquidity premia in
government bonds.** *NBER Working Paper* 16892.
[https://doi.org/10.3386/w16892](https://doi.org/10.3386/w16892)

**Primary methodology:** Asness, C. S., Moskowitz, T. J. & Pedersen,
L. H. (2013). **Value and momentum everywhere.** *Journal of Finance*,
68(3), 929–985.
[https://doi.org/10.1111/jofi.12021](https://doi.org/10.1111/jofi.12021)

BibTeX entries: `pfluegerViceira2011tips` (foundational) and
`asness2013value` (primary, already aggregated by `bond_tsmom_12_1`).

## Why two papers

Pflueger/Viceira (2011) decomposes TIPS yields into a real-rate
component and a liquidity premium and documents that *real* yields
exhibit persistent mean-reverting dynamics. They do not prescribe a
trading rule; the role of this paper is to establish that real
yields are a meaningful, mean-reverting state variable distinct from
nominal yields.

Asness/Moskowitz/Pedersen (2013) §V documents that 12/1 time-series
momentum produces positive risk-adjusted returns on bond futures
across G10 markets. The same momentum rule generalises to TIPS
real-yield-derived bond returns, because the underlying mechanism —
trend persistence at horizons of 1–12 months — applies to any
sufficiently long-running bond price series.

The synthesis: take the canonical Asness §V 12/1 momentum rule and
apply it to a real-yield-derived bond return series instead of a
nominal-yield-derived one.

## Differentiation from `bond_tsmom_12_1`

The two strategies share the same momentum mechanic but trade
*different* underlying signals:

* **`bond_tsmom_12_1`** — nominal bond returns. Sensitive to the
  parallel-shift PC1 of the *nominal* yield curve.
* **`real_yield_momentum`** (this strategy) — TIPS real-yield bond
  returns. Sensitive to the parallel-shift PC1 of the *real* yield
  curve.

The two are highly correlated during regime-stable periods (when
nominal and real yields move together via parallel shifts in
inflation expectations) but decouple during inflation-regime shocks
(2008-09 deflation scare, 2020 March, 2021-22 inflation surge).
Expected ρ ≈ 0.6-0.8.

## Published rules

For each month-end *t*:

1. Compute trailing return over months ``[t−12, t−1)`` on the
   real-yield-derived bond price series.
2. Sign-of-return signal: +1 if positive, −1 if negative, 0 if
   ``|return| ≤ threshold``.
3. Hold one month, rebalance monthly.

| Parameter | Default | Notes |
|---|---|---|
| `lookback_months` | `12` | 12/1 convention |
| `skip_months` | `1` | skip most-recent month |
| `threshold` | `0.0` | filter marginal signals |

## TIPS bond-return approximation

For real-feed Session 2H benchmarks running on FRED's `DFII10`
constant-maturity TIPS yield rather than TIP (the ETF), convert
real yield changes to bond-return-equivalent prices via::

    real_bond_return ≈ -duration * Δ(real_yield)

Default duration for the 10Y TIPS is 7.5 years (slightly lower than
the 8.0-year nominal because TIPS amortise principal partly through
inflation accrual). The approximation drops convexity and the
inflation-accrual term; the *sign* of any 11-month cumulative
real-bond-return is preserved because both terms bias the *level*
of returns.

## Implementation deviations from Asness §V

Identical to `bond_tsmom_12_1`:

1. **No vol-targeting** — single-asset application has no cross-
   instrument sizing to perform.
2. **No transaction-cost or short-borrow model** — bridge applies
   ``commission_bps``.
3. **Threshold parameter** (default `0.0`) — small departure from
   the pure sign rule.

None of these change the *sign* of the signal relative to the
paper.

## Asset class note

Where most TSMOM literature documents the strategy on *nominal*
sovereign bonds, this implementation is on *real* (inflation-
indexed) bonds. The economic content is the same (trend-following
on a stationary risk factor), but the realisations diverge during
inflation shocks. Pflueger/Viceira (2011) documents that real
yields are a distinct state variable from nominal yields — this
strategy isolates exposure to that variable.
