# Paper — Breakeven Inflation Rotation (FLL 2014, after Campbell/Shiller 1996)

## Citations

**Initial inspiration:** Campbell, J. Y. & Shiller, R. J. (1996).
**A scorecard for indexed government debt.** *NBER Macroeconomics
Annual*, 11, 155–197.
[https://doi.org/10.2307/3585242](https://doi.org/10.2307/3585242)

**Primary methodology:** Fleckenstein, M., Longstaff, F. A. &
Lustig, H. (2014). **The TIPS-Treasury bond puzzle.** *Journal of
Finance*, 69(5), 2151–2197.
[https://doi.org/10.1111/jofi.12032](https://doi.org/10.1111/jofi.12032)

BibTeX entries: `campbellShiller1996scorecard` (foundational) and
`fleckensteinLongstaffLustig2014tips` (primary) in
`docs/papers/phase-2.bib`.

## Why two papers

Campbell/Shiller (1996) provides the *risk-factor* analytical
framework for inflation-indexed government debt: the term structure
of breakeven inflation decomposes into expected-inflation and
inflation-risk-premium components, both of which are stationary
mean-reverting variables.

Fleckenstein/Longstaff/Lustig (2014) provides the *expected-return*
result: by replicating TIPS cash flows synthetically with
inflation swaps, they show a TIPS-Treasury basis as large as 200
bps existed during 2008-2009 and converged subsequently. The basis
is therefore a tradeable mispricing, and trading it on extreme
deviations from fair value has positive expected return.

The synthesis: Campbell/Shiller establish that the breakeven
inflation rate is mean-reverting around its long-run mean;
Fleckenstein/Longstaff/Lustig establish that trading the deviation
makes economic sense. Neither paper specifies the explicit
"breakeven extreme → rotate TIPS vs nominal" rule; that rule is a
practitioner synthesis of the two results.

## Rotation mechanics

A 10Y TIPS and a 10Y nominal Treasury have similar duration but
different inflation exposure:

* The nominal Treasury pays a fixed coupon → exposed to surprise
  inflation (loses real value when inflation rises).
* The TIPS pays a real coupon plus an inflation adjustment to
  principal → hedged against surprise inflation.

The breakeven inflation rate ``B = Y_nominal − Y_TIPS`` represents
the market's pricing of expected inflation plus an inflation-risk
premium.

* **B high** vs history ↔ market pricing high inflation
  expectations ↔ TIPS expensive vs nominals → **short-TIPS**
  rotation (long nominal, short TIPS) when reversion expected.
* **B low** vs history ↔ market pricing low inflation expectations ↔
  TIPS cheap vs nominals → **long-TIPS** rotation when reversion
  expected.

## Breakeven proxy from prices

Direct breakeven yield computation requires FRED's `T10YIE` series.
The price-space proxy used here exploits the duration-symmetry of
matched-maturity TIPS and nominal Treasuries:

    log_spread = log(P_TIPS) − log(P_nominal)

When breakeven yield rises (``Y_nominal − Y_TIPS`` increases), the
nominal price falls more than the TIPS price (the nominal is
re-pricing higher real yields), so ``log_spread`` *increases*.
Mean-reversion of breakeven manifests as mean-reversion of
``log_spread`` in the opposite direction.

## Published rules

For each daily bar:

1. ``log_spread = log(P_TIPS) − log(P_nominal)``.
2. ``z = (log_spread − rolling_mean) / rolling_std`` over a 252-day
   trailing window.
3. **Short-TIPS rotation:** ``z > +entry_threshold``. Set TIPS
   weight = -1, nominal weight = +1.
4. **Long-TIPS rotation:** ``z < -entry_threshold``. Set TIPS
   weight = +1, nominal weight = -1.
5. **Exit** when ``|z| < exit_threshold``.

| Parameter | Default | Notes |
|---|---|---|
| `zscore_window` | `252` | ≈ 1 year |
| `entry_threshold` | `1.0` σ | enter on ±1σ extreme |
| `exit_threshold` | `0.25` σ | hysteresis avoids whipsaw |

Position sizing is equal dollar weight on each leg (±1.0). The
duration mismatch in real ETFs (TIP duration ≈ 7.5 vs IEF duration
≈ 8.0) is small but documented as a known failure.

## In-sample period (Fleckenstein/Longstaff/Lustig 2014)

* Data: 2003–2011 (CRSP fixed-income files + Bloomberg inflation
  swaps)
* Documents basis as large as 200 bps in 2008-2009; convergence
  to under 50 bps by 2011.
* Sharpe of the explicit TIPS-Treasury basis arbitrage (using
  inflation swaps to hedge inflation exposure) is reported as
  consistently positive in the post-crisis convergence period.

The implementation here trades a *simplified* version of the basis
(without explicit inflation-swap hedging) and is therefore exposed
to inflation realisation surprises — this is documented in
`known_failures.md`.

## Implementation deviations from the source papers

1. **No inflation-swap hedge.** FLL's pure arbitrage uses inflation
   swaps to strip out the inflation exposure on TIPS. This
   implementation trades the unhedged TIPS-vs-nominal price
   difference, leaving residual exposure to inflation surprises.
   This is a major deviation; documented prominently in paper.md
   and known_failures.md.
2. **ETF basket vs constant-maturity matching.** The default ETF
   universe (TIP / IEF) does not perfectly match maturities or
   duration. Real-feed Session 2H benchmarks should construct a
   matched-maturity TIPS/nominal pair from FRED's `DFII10` and
   `DGS10` constant-maturity yields.
3. **Mean-reversion entry rule** rather than fair-value-deviation
   threshold from a model. FLL uses an explicit fair-value model
   based on cash-flow replication; this implementation uses the
   simpler z-score-on-spread.

## Known replications and follow-ups

* **Pflueger & Viceira (2011)** — "An Empirical Decomposition of
  Risk and Liquidity Premia in Government Bonds", JFQA. Refined
  decomposition that supports the mean-reversion thesis.
* **Adrian, Crump & Moench (2013)** — TIPS-specific term-structure
  estimates with priced inflation risk.
