# Paper — Cross-Sectional Commodity Curve Carry (KMPV 2018 §IV)

## Citations

**Foundational paper:** Erb, C. B. & Harvey, C. R. (2006). **The
strategic and tactical value of commodity futures.** *Financial
Analysts Journal*, 62(2), 69–97.
[https://doi.org/10.2469/faj.v62.n2.4084](https://doi.org/10.2469/faj.v62.n2.4084)

EH06 §III formalises the single-asset curve-carry rule on a
commodity panel. Single-asset expressions are shipped as
`wti_backwardation_carry` (long-only WTI) and `ng_contango_short`
(short-only NG); this strategy is the cross-sectional
generalisation.

**Primary methodology:** Koijen, R. S. J., Moskowitz, T. J.,
Pedersen, L. H. & Vrugt, E. B. (2018). **Carry.** *Journal of
Financial Economics*, 127(2), 197–225.
[https://doi.org/10.1016/j.jfineco.2017.11.002](https://doi.org/10.1016/j.jfineco.2017.11.002)

KMPV 2018 unifies "carry" across asset classes (currencies, bonds,
equities, commodities, options) under a single signal: the return
the asset earns *if prices do not change*. For commodity futures,
that signal is the **roll yield** ``(F1 - F2) / F2`` — identical to
the EH06 §III curve slope.

Section IV (commodity-specific) reports a long-short cross-
sectional carry book Sharpe of ~0.7 over 1980-2012 on a
24-commodity panel. The strategy ranks all constituents by roll
yield, longs the top quantile and shorts the bottom.

BibTeX entries `erbHarvey2006` and `koijen2018carry` are
registered in `docs/papers/phase-2.bib`. No new bib entries are
needed for this commit.

## Why cross-sectional vs single-asset

The single-asset expressions (`wti_backwardation_carry`,
`ng_contango_short`) and the cross-sectional rank capture
different practitioner allocations:

* **Single-asset**: clean expression on a specific commodity,
  no cross-sectional dilution. Useful when the user has a view
  on that commodity's curve specifically.
* **Cross-sectional rank**: diversified KMPV §IV carry premium,
  trades both legs of the curve across the full panel, captures
  the cross-sectional dispersion that lifts the long-run Sharpe.

Both ship because the choice of expression is itself the point —
not a duplicate strategy. The predicted ρ between the strategies
is 0.3-0.6 (documented in `known_failures.md`), well below the
master plan §10 deduplication bar (ρ > 0.95).

## Differentiation from sibling carry strategies

* **`wti_backwardation_carry`** — single-asset long-only WTI.
  Predicted ρ ≈ 0.4-0.6 with this strategy when crude is in the
  long tail of the rank (it usually is — crude is the largest
  carry contributor in the panel).
* **`ng_contango_short`** — single-asset short-only NG. Predicted
  ρ ≈ 0.3-0.5 in summer-contango months (NG is typically in the
  short tail), lower in winter.
* **`commodity_tsmom`** — cross-sectional momentum on the same
  panel. Different signal entirely (trailing returns, not curve
  slope). When momentum and carry align (steep-curve trending
  regimes), ρ ≈ 0.3-0.5; otherwise ρ ≈ 0.1-0.3.
* **Phase 1 `tsmom_12_1`** (trend family) — different signal,
  different universe. ρ ≈ 0.2-0.3.

## Cross-sectional rank rule

At each month-end *t*:

1. For each commodity *c*, compute the smoothed roll yield
   ``(F1_c - F2_c) / F2_c`` (21-day rolling mean of daily
   observations).
2. Rank all commodities cross-sectionally by smoothed roll yield.
3. **Long** the top ``top_quantile`` (most-backwardated).
4. **Short** the bottom ``bottom_quantile`` (most-contangoed).
5. Equal-weight within each leg; dollar-neutral when
   ``top_quantile == bottom_quantile``.

| Parameter | KMPV §IV value | AlphaKit default | Notes |
|---|---|---|---|
| Curve metric | (F1 − F2) / F2 | (F1 − F2) / F2 | identical |
| Smoothing | end-of-month observation | 21-day rolling mean | KMPV uses month-end snapshots; we smooth daily for tighter signal-to-noise |
| Top quantile | top 1/3 (typical) | 1/3 | matches KMPV exposition |
| Bottom quantile | bottom 1/3 (typical) | 1/3 | matches KMPV exposition |
| Panel size | 24 commodities | 8 (default) | smaller universe penalty (see below) |
| Rebalance | monthly | monthly | identical |

### Why an 8-commodity default panel

KMPV §IV uses a 24-commodity panel (NYMEX/ICE energy, COMEX/LME
metals, CBOT/Kansas grains, ICE softs, CME livestock). The default
AlphaKit panel is 8 (CL, NG, GC, SI, HG, ZC, ZS, ZW), matching
`commodity_tsmom`'s default for cross-strategy consistency.
Users can override `front_next_map` to expand or shrink the
universe.

The smaller panel attenuates the cross-sectional dispersion that
drives the long-run Sharpe — KMPV §IV reports ~0.7 on the
24-commodity panel; the 8-commodity AlphaKit default is expected
to come in at 0.3-0.5 OOS. Trade-off: the 8-commodity panel uses
exclusively yfinance-available `=F` symbols with documented data,
while the broader 24-commodity panel requires explicit-contract
data feeds (deferred to Session 2H).

## In-sample period (KMPV 2018 §IV)

* Data: 1980-2012 commodity-futures panel, 24 commodities, monthly
* Cross-sectional carry Sharpe ~0.7
* Out-of-sample (Levine et al. 2018): 2005-2016 carry Sharpe ~0.4
  on a 20-commodity panel — meaningful degradation but persistence
  of the premium

For the AlphaKit 8-commodity default we expect:

* **Long-window OOS Sharpe (2005-2025)**: 0.3-0.5
* **Steep-curve regimes (2008 H1 commodity bubble, 2022 H1 energy
  crisis)**: Sharpe 0.7-1.0 with low drawdown
* **Flat-curve regimes (2014-15 commodity glut, 2020 H1 COVID)**:
  Sharpe 0.0-0.3 — weak signal, high turnover, low edge

## Implementation deviations from KMPV §IV

1. **Daily smoothed signal instead of month-end snapshot.** Same
   rationale as the single-asset siblings: 21-day rolling mean is
   more robust to roll-day noise than a single end-of-month
   observation.
2. **8-commodity default vs KMPV's 24.** Smaller universe penalty
   on long-run Sharpe (see "Why an 8-commodity default panel").
3. **Equal-weighted within terciles.** KMPV §IV uses signal-
   weighted positions (proportional to roll yield). Equal-weighting
   is robust to outliers; signal-weighting is a Phase 3 candidate
   that requires careful position-sizing scaffolding.
4. **No bid-ask, financing, or short-borrow model.** The bridge
   applies a flat `commission_bps` per leg.

None of these change the **economic content** of the KMPV §IV
cross-sectional carry rule.

## KMPV (2018) abstract excerpt

> ... we define the carry of a security as the futures-implied
> expected return assuming that prices do not change. Carry is
> related but distinct from value, momentum, and the term spread.
> A market-neutral portfolio that goes long high-carry assets and
> short low-carry assets earns significant returns in each of the
> asset classes we study, with a global average annualised Sharpe
> ratio of about 0.7 ...

## Known replications and follow-ups

* **Erb & Harvey (2006) §III** — single-asset commodity carry,
  foundational and still cited by the EH06 single-asset siblings.
* **Levine, Ooi, Richardson, Sasseville (2018)** — "Commodities
  for the Long Run", FAJ 74(2). Updates the KMPV result through
  2016 and decomposes the premium into curve and momentum
  components.
* **Asness, Moskowitz, Pedersen (2013)** — "Value and Momentum
  Everywhere", JF 68(3). Cross-asset value and momentum
  framework; complements KMPV's carry framework.
