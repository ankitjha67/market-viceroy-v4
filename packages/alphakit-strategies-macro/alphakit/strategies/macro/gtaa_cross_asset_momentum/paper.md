# Paper — Cross-Asset GTAA Time-Series Momentum (AMP §V, 2013)

## Citations

**Initial inspiration:** Hurst, B., Ooi, Y. H. & Pedersen, L. H.
(2017). **A Century of Evidence on Trend-Following Investing.**
*Journal of Portfolio Management* 44(1), 15-29.
[https://doi.org/10.3905/jpm.2017.44.1.015](https://doi.org/10.3905/jpm.2017.44.1.015)

**Primary methodology:** Asness, C. S., Moskowitz, T. J. & Pedersen,
L. H. (2013). **Value and Momentum Everywhere.** *Journal of
Finance* 68(3), 929-985. Section V applies the 12/1 time-series-
momentum rule across four asset classes (equity index futures,
government bonds, currencies, commodities) and documents a
diversified-cross-asset Sharpe substantially higher than any single-
asset-class application of the same rule.
[https://doi.org/10.1111/jofi.12021](https://doi.org/10.1111/jofi.12021)

BibTeX entries: `hurstOoiPedersen2017century` (foundational) and
`asness2013value` (primary) in `docs/papers/phase-2.bib`. AMP 2013
is already registered by `bond_tsmom_12_1`, `commodity_tsmom`, and
`metals_momentum` in earlier commits and reused here; HOP 2017 is
new in this commit.

## Why two papers

AMP (2013) §V is the *implementation anchor* — it specifies the
cross-asset universe, the 12/1 lookback, and the inverse-vol
position-sizing rule. The §V case study documents Sharpe ratios in
the 0.8–1.0 range for the diversified four-asset-class book over
1972–2009 — materially higher than any single-asset-class
application of the same rule.

HOP (2017) is the *long-horizon validation*. Where AMP §V documents
the result on 1972–2009 (37-year sample), HOP extends the analysis
to **1880–2013** across 67 markets. The 134-year out-of-sample
confirmation establishes that the TSMOM premium is not an artefact
of any specific market regime — the cross-asset trend-following book
earned positive risk-adjusted returns in the gold-standard era
(1880-1914), the inter-war period (1918-1939), Bretton Woods
(1944-1971), and the floating-rate era (1973-present).

Implementation replicates AMP §V's rule verbatim (12/1 sign-of-
return with per-asset inverse-vol scaling) on a 9-ETF cross-asset
panel — the ETF-substrate version of AMP's futures universe. The
expected Sharpe band reflects both anchors: AMP's reported 0.8–1.0
on the full-breadth futures panel, scaled down for the narrower
9-ETF universe and the daily-bar substrate.

## Differentiation from sibling momentum strategies

* **Phase 1 `tsmom_12_1`** (trend family) — same 12/1 TSMOM
  mechanic but with a narrower 6-ETF universe ``(SPY, EFA, EEM,
  AGG, GLD, DBC)`` and cited on **Moskowitz/Ooi/Pedersen 2012** as
  the primary anchor. Three load-bearing differentiations:
    1. **Universe breadth.** This strategy adds ``TLT`` (long
       Treasuries, duration risk), ``HYG`` (high-yield credit, a
       distinct risk factor from aggregate bonds), and ``VNQ``
       (US REITs, a separate real-asset class). The 9-asset panel
       covers four asset super-classes; the Phase 1 6-asset panel
       covers three (no real estate, no credit, no long-duration).
    2. **Citation anchor.** AMP 2013 §V (cross-asset case study)
       rather than MOP 2012 (foundational TSMOM). HOP 2017 is the
       century-of-evidence extension that the Phase 1 trend
       strategy does not cite.
    3. **Cluster identity.** This strategy is positioned in the
       *macro family* as a GTAA (global tactical asset allocation)
       implementation. The Phase 1 strategy is positioned in
       *trend* as the canonical multi-asset TSMOM reference.
       Cluster analysis treats them as siblings, not duplicates.
  Expected ρ with Phase 1 `tsmom_12_1`: **0.65–0.85** when
  cross-asset momentum signals align (typical in trending macro
  regimes), lower when the added TLT / HYG / VNQ legs diverge
  from the 6-ETF base universe. Documented as cluster-risk
  acceptance in `known_failures.md`.
* **Phase 1 `dual_momentum_gem`** (trend family) — Antonacci's
  3-asset absolute + relative momentum on US equity / Intl equity
  / bonds with discrete 100%-allocation switching. Same overall
  asset-allocation theme but discrete vs continuous weighting.
  Expected ρ ≈ 0.30–0.50.
* **Phase 2 `commodity_tsmom`** (commodity family) — same TSMOM
  mechanic on commodity futures only. Different asset class;
  expected ρ ≈ 0.30–0.50 when commodities (GLD/DBC overlap)
  dominate the cross-asset trend, lower otherwise.
* **Phase 2 `bond_tsmom_12_1`** (rates family) — single-asset
  10Y treasury TSMOM. Overlaps with the TLT leg of this strategy;
  expected ρ ≈ 0.20–0.40.
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  static 25/25/25/25 allocator on a similar broad-asset universe.
  Expected ρ ≈ 0.40–0.60 in trending regimes (when GTAA momentum
  agrees with permanent-portfolio constituents) and lower in
  mean-reverting regimes.

## Published rules (AMP §V applied to a cross-asset ETF panel)

For each asset *a* and each month-end *t*:

1. Compute the trailing return over the 12 months ending one month
   prior — months ``[t-12, t-1)``. Skip the most recent month per
   the 12/1 convention (sidesteps short-term reversal).
2. **Sign-of-return** trade: long if positive, short if negative.
3. **Per-asset volatility scaling** to a constant target (10%
   annualised by default). Position size for asset *a* at month
   *t*::

       weight_a(t) = sign(lookback_return_a) × (vol_target / realised_vol_a)

4. Hold one month, rebalance monthly.

| Parameter | AMP §V value | AlphaKit default | Notes |
|---|---|---|---|
| Lookback | 12 months | 12 months | identical |
| Skip | 1 month | 1 month | identical |
| Vol target (per asset) | 40% annualised | 10% annualised | rescaled to portfolio level (see below) |
| Vol estimator | EWMA, 60-day half-life | 63-day rolling σ | converges to same long-run estimate |
| Universe | Futures across 4 asset classes | 9-ETF panel across 4 super-classes | substrate translation; see Data Fidelity |
| Rebalance | monthly | monthly | identical |
| Holding period | 1 month | 1 month | identical |

### Why the rescaled vol target

AMP §V targets **40% volatility per instrument** because the futures
panel diversifies across many instruments and the gross-leverage
budget is around 2-3×. When applied to a tractable 9-ETF universe,
the 40% per-asset target produces a portfolio volatility well above
any practitioner risk budget. Rescaling to 10% per-asset brings the
9-ETF portfolio volatility into the 8–12% range that asset owners
typically benchmark against.

The *sign* and *relative* sizing are unchanged — only the absolute
scale is rescaled. All headline metrics (Sharpe, Sortino, Calmar)
are scale-invariant, so results remain directly comparable to the
paper.

## Data Fidelity

* **Substrate:** daily closing prices from yfinance for 9 ETFs.
  All ETFs have inception dates before 2007 (the binding constraints
  are EEM 2003, EFA 2001, AGG 2003, TLT 2002, HYG 2007, DBC 2006,
  VNQ 2004). The continuous panel begins 2007-04 once HYG is live.
* **ETF substrate vs futures substrate.** AMP §V uses futures
  contracts; this implementation uses ETFs. ETFs introduce slight
  tracking differences (NAV vs futures price, dividends reinvested
  vs roll yield), but the 12-month momentum signal is robust to
  these — the sign of the 12-month return is preserved under any
  reasonable substrate translation. The benchmark numbers are
  expected to be slightly different from AMP §V's reported Sharpe
  on the futures panel; the *sign* of the strategy's edge is
  preserved.
* **Real-estate substrate.** VNQ (US REITs) is the cleanest
  pre-2010 real-estate exposure on yfinance. Phase 3 users with
  international real-estate data may wish to add ``RWX`` (developed
  ex-US REITs) and ``DRW`` (emerging-market real estate) — out of
  scope for the AlphaKit substrate.
* **No transaction costs in synthetic fixture.** The vectorbt
  bridge applies a configurable flat ``commission_bps`` per
  rebalance leg. The in-repo benchmark in
  ``benchmark_results.json`` reports headline metrics at
  ``commission_bps = 5.0``.
* **Rebalance cadence:** monthly target signal, daily bridge-side
  drift correction (AlphaKit-wide convention; see Session 2G
  amendment "alphakit-wide rebalance-cadence convention" in
  ``docs/phase-2-amendments.md``).

## Expected Sharpe range

`0.5 – 0.8 OOS`. The lower bound of 0.5 accounts for the AlphaKit
ETF substrate (vs AMP §V's futures panel) and the narrower 9-asset
universe (vs AMP's broader futures cross-section). The upper bound
of 0.8 reflects AMP §V Table III's reported 0.8 Sharpe on the
multi-asset book over 1972–2009. HOP (2017) Table 2 reports a Sharpe
of 0.7 on the century-long sample, which sits in the middle of the
predicted range.

## Implementation deviations from AMP §V / HOP 2017

1. **ETF substrate** instead of AMP's futures contracts. See "Data
   Fidelity" above. The momentum signal sign is preserved; absolute
   Sharpe numbers may differ by a few basis points.
2. **Rolling σ instead of EWMA.** Both estimators converge to the
   same long-run realised volatility; the rolling window is chosen
   here for *reproducibility* — the weights are deterministic
   functions of the input prices, without exponential-decay state
   to seed. The same choice was made by the Phase 2 sibling
   strategies (`bond_tsmom_12_1`, `commodity_tsmom`,
   `metals_momentum`) for consistency.
3. **Per-asset leverage cap of 3×** so a collapse in realised
   volatility cannot push weights to infinity. AMP §V does not
   need this because EWMA estimators are smoother; the cap is a
   substrate-engineering safety belt.
4. **Portfolio-level vol target of 10%** instead of the paper's
   per-asset 40%. See "Why the rescaled vol target" above.
5. **No bid-ask, financing, or short-borrow model.** The bridge
   applies a flat ``commission_bps`` per leg. AMP's reported
   Sharpe figures net of typical futures friction would
   approximately equate.

None of these change the **sign** of the signal or the **relative
ordering** of weights, so the strategy remains faithful to the
paper's economic content.

## Known replications and follow-ups

* **Faber, M. (2007)** — *A Quantitative Approach to Tactical
  Asset Allocation*, JoWM Spring 2007 / SSRN 962461. Five-asset
  GTAA with a 10-month moving-average overlay; the same broad-
  multi-asset framing on an ETF substrate.
* **Baltas, A. N. & Kosowski, R. (2013)** — *Momentum Strategies
  in Futures Markets and Trend-Following Funds*, EFA. Replicates
  AMP §V with updated data and decomposes the contribution by
  asset class — confirms that cross-asset diversification is the
  Sharpe-multiplier.
* **Asness, C. S. (2014)** — *My Top 10 Peeves*, FAJ. Argues that
  the TSMOM signal's persistence is not a market inefficiency
  but a behavioural risk premium consistent with delayed-
  reaction theories. Useful framing for the strategy's
  expected-return rationale.
