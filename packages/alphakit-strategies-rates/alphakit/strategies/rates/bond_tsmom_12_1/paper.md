# Paper — Time-Series Momentum on Bonds (Asness §V, 2013)

## Citations

**Initial inspiration:** Moskowitz, T. J., Ooi, Y. H. & Pedersen, L. H.
(2012). **Time series momentum.** *Journal of Financial Economics*,
104(2), 228–250. [https://doi.org/10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003)

**Primary methodology:** Asness, C. S., Moskowitz, T. J. & Pedersen,
L. H. (2013). **Value and momentum everywhere.** *Journal of Finance*,
68(3), 929–985. Section V applies the 12/1 time-series-momentum rule
to 10-year sovereign bond futures across G10 markets.
[https://doi.org/10.1111/jofi.12021](https://doi.org/10.1111/jofi.12021)

BibTeX entries are aggregated in `docs/papers/phase-2.bib` under
`moskowitz2012tsmom` (foundational) and `asness2013value` (primary).

## Why two papers

Moskowitz/Ooi/Pedersen (2012) is the seminal *time-series-momentum*
paper but documents the strategy primarily on a 58-instrument
multi-asset futures panel. The bond-only application — what this
strategy implements — is a Section V case study in
Asness/Moskowitz/Pedersen (2013), which extends the 12/1 rule to G10
sovereign bond futures and confirms positive risk-adjusted returns
for the bond-only sub-strategy. We anchor the implementation on
Asness §V because that is the section whose methodology is replicated
verbatim; we cite Moskowitz 2012 as the foundational reference.

## Published rules (Asness §V applied to a single bond)

For each month-end *t*:

1. Compute the trailing return over the 12 months ending one month
   prior — months ``[t-12, t-1)``. Skip the most recent month per
   the 12/1 convention (sidesteps short-term reversal).
2. **Sign-of-return** trade: long if positive, short if negative.
3. Hold one month, rebalance at next month-end.

| Parameter | Asness §V value | AlphaKit default | Notes |
|---|---|---|---|
| Lookback | 12 months | 12 months | identical |
| Skip | 1 month | 1 month | identical |
| Vol target | constant per asset (10% by Asness convention) | none (raw signal) | single-asset; vol overlay deferred to portfolio layer |
| Rebalance | monthly | monthly | identical |
| Holding period | 1 month | 1 month | identical |

## Asness §V abstract excerpt (relevant fragment)

> ... time-series momentum is a robust phenomenon. We document
> significant time-series momentum in equity index, currency,
> commodity, and bond futures. The strategy is profitable for each
> of the four asset classes ... A diversified time-series-momentum
> strategy across all asset classes delivers substantial abnormal
> returns ...

The bond-only sub-strategy in §V earns a Sharpe of approximately
0.7–1.0 over 1985–2010 on the G10 sovereign-bond panel, with the
single-country (10-year US Treasury) sub-strategy in the 0.4–0.6
range. Single-asset application without vol-targeting (this
implementation) typically falls below those bands; see
[`known_failures.md`](known_failures.md).

## Bond-return approximation (FRED-only fallback)

The strategy operates on a price-like DataFrame. When the only feed
available is FRED's `DGS10` (constant-maturity 10-year yield) and not
a tradeable bond ETF, callers must pre-convert yield changes to
approximate bond returns via the standard duration approximation::

    bond_return ≈ -duration * delta_yield

For the 10Y constant-maturity series the modified duration is
approximately 8 years (varies with the yield level). The approximation
drops:

* **Convexity term** (½ × convexity × Δy²): negligible at typical
  monthly Δy ≤ 50 bps; convexity ≈ 80 for the 10Y, so
  ½ × 80 × (0.005)² = 0.001 (10 bps). Compared to the duration
  term (8 × 0.005 = 0.04 = 400 bps), the convexity correction is
  roughly 40× smaller, biasing the level of returns by a small
  fraction.
* **Carry term** (yield × dt): pure carry adds yield/12 ≈ 30–40 bps
  per month at current rates. This biases the **level** of returns
  upward but **not the sign** of any 11-month sum.

The 12/1 momentum signal depends on the *sign* of the cumulative
return, which is dominated by duration × Δy at typical horizons. The
approximation is therefore acceptable for signal generation but **not**
for accurate P&L attribution. Real-feed Session 2H benchmarks should
prefer TLT total-return prices over yield-derived approximations.

## In-sample period (Asness §V)

* Data: 1985–2010 (G10 bond futures, monthly rebalances)
* Out-of-sample: 1973–2009 OOS for the bond-only sub-strategy
* The Sharpe ratios reported in §V are for the *diversified*
  cross-asset and cross-country book; single-bond sub-strategies
  underperform the diversified composite — this is expected and is
  documented in `known_failures.md`.

## Implementation deviations from Asness §V

1. **No volatility targeting.** Asness §V scales each instrument to a
   constant volatility target (10% annualised) and combines them into
   a diversified book. On a single bond there is no cross-instrument
   sizing to perform, so we expose the raw {−1, 0, +1} signal and
   defer vol-targeting to a portfolio overlay (or to a future
   multi-bond rates strategy).
2. **No bid-ask / financing cost model.** Asness reports gross
   returns; AlphaKit benchmarks reapply transaction costs via the
   bridge's `commission_bps` parameter, but financing costs for
   short bond positions are not modelled.
3. **Threshold parameter** (default `0.0`). Setting `threshold > 0`
   filters out marginal signals; this is a small departure from the
   pure sign rule of the paper. Documented as a config knob, not a
   methodological deviation.

None of these change the **sign** of the signal relative to the paper.

## Known replications and follow-ups

* **Hurst, Ooi & Pedersen (2017)** — "A Century of Evidence on
  Trend-Following Investing", AQR. Extends Asness/MOP to 1880 and
  reproduces the bond-momentum result on long-horizon data.
* **Baltas & Kosowski (2013)** — "Momentum Strategies in Futures
  Markets and Trend-Following Funds", EFA Annual Meeting paper.
  Replicates Asness §V with updated data and decomposes contribution
  by asset class.
