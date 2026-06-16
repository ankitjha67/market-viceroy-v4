# Paper — WTI Crude-Oil Backwardation Carry (Erb/Harvey 2006 §III)

## Citations

**Foundational paper:** Gorton, G. & Rouwenhorst, K. G. (2006).
**Facts and fantasies about commodity futures.** *Financial Analysts
Journal*, 62(2), 47–68.
[https://doi.org/10.2469/faj.v62.n2.4083](https://doi.org/10.2469/faj.v62.n2.4083)

GR06 establishes the empirical case that the long-run excess return
on commodity futures is dominated by **roll yield** — the return
earned on a long position as a backwardated curve rolls down toward
spot. Curve slope, not spot price appreciation, is the empirical
engine of the commodity risk premium.

**Primary methodology:** Erb, C. B. & Harvey, C. R. (2006). **The
strategic and tactical value of commodity futures.** *Financial
Analysts Journal*, 62(2), 69–97.
[https://doi.org/10.2469/faj.v62.n2.4084](https://doi.org/10.2469/faj.v62.n2.4084)

Section III ("The Term Structure Story") turns the GR06 observation
into a *tactical* allocation rule: long backwardated commodities,
flat or underweight contangoed commodities. EH06 documents the rule
on the 1982-2004 commodity panel and reports a long-short Sharpe of
~0.6 between the most-backwardated and most-contangoed commodities.

BibTeX entries `gortonRouwenhorst2006` and `erbHarvey2006` are
registered in `docs/papers/phase-2.bib`.

## Why WTI specifically

Crude oil exhibits the most pronounced and persistent backwardation
in the commodity panel (driven by storage and convenience-yield
dynamics: oil is costly to store, and unscheduled demand shocks bid
up the front contract relative to the back of the curve). Per EH06
Table III, the WTI carry sub-strategy posts a Sharpe of ~0.6 over
1982-2004 — the highest single-commodity carry Sharpe in the panel.

We ship a WTI-specific strategy because:

1. The WTI carry trade is the canonical demonstration of the EH06
   §III rule and a standard sleeve in real-money commodity-overlay
   programs.
2. Single-commodity carry is a cleaner expression than the broader
   `commodity_curve_carry` (Commit 6) which ranks across the panel
   — the ranked book diversifies but obscures the per-asset risk
   premium that EH06 specifically attributes to crude.
3. Crude carry has its own well-documented failure mode (2014-15
   oil glut, 2020 negative-prices event) that is asymmetric versus
   the panel — see `known_failures.md`.

## Differentiation from sibling carry strategies

* **`ng_contango_short`** (Session 2E sibling) — short-only natural-
  gas contango trade. Same EH06 §III economic logic but on the
  *short* side of contangoed commodities, with NG-specific storage
  microstructure. ρ with `wti_backwardation_carry` ≈ 0.0-0.2 (gas
  and oil curves trade different physical regimes).
* **`commodity_curve_carry`** (Session 2E sibling, Commit 6) —
  cross-sectional rank-based carry on the broader 8-commodity panel
  (KMPV 2018 §IV methodology). ρ with `wti_backwardation_carry` ≈
  0.4-0.6 when crude contributes meaningfully to the cross-section
  (it usually does — crude is the largest carry contributor in the
  panel).
* **Trend-family `tsmom_12_1`** (Phase 1) — different signal entirely
  (trailing 12/1 returns, not curve slope). ρ ≈ 0.2-0.4.

## Curve-slope signal

For each trading day *t*::

    roll_yield(t) = (F1(t) - F2(t)) / F2(t)

where ``F1`` is the front-month contract and ``F2`` is the next-
listed-month contract. Positive = backwardation (curve slopes
downward); negative = contango (curve slopes upward).

The raw daily series is noisy (intra-day mark-to-market jitter,
end-of-month roll mechanics, holiday-week distortions). We smooth
with a 21-day rolling mean before the signal so the strategy does
not flip on single-day curve flickers.

| Parameter | EH06 §III value | AlphaKit default | Notes |
|---|---|---|---|
| Curve metric | (F1 − F2) / F2 | (F1 − F2) / F2 | identical |
| Smoothing | end-of-month observation | 21-day rolling mean | EH06 uses month-end snapshots; we smooth daily for a tighter signal-to-noise tradeoff |
| Signal threshold | > 0 long, < 0 short | > 0 long, else flat | long-only; the short-contango leg is in `ng_contango_short` |
| Rebalance | monthly | daily | smoother daily evaluation; reduces month-end signal-flip jitter |

## Trading rule

Long-only per EH06 §III:

* smoothed roll yield > ``backwardation_threshold`` → **+1** (long
  the front-month contract)
* otherwise → **0** (cash)

We deliberately do **not** short contango here. Shorting contango
is a different trade with different microstructure (storage costs,
short-borrow availability, contango-trap risk in deep-contango
regimes); `ng_contango_short` handles that case explicitly for
natural gas, where the contango microstructure is well-documented.

## In-sample period (Erb/Harvey §III)

* Data: 1982-2004 commodity-futures panel
* WTI carry sub-strategy reported Sharpe ~0.6
* Out-of-sample (Levine et al. 2018): 2005-2016 long-only WTI
  backwardation Sharpe ~0.3 — meaningfully degraded by the 2014-15
  oil glut (deep-and-persistent contango regime that the strategy
  correctly stays flat through but does not benefit from)

For the AlphaKit default we expect:

* **Long-window OOS Sharpe (2005-2025)**: 0.2-0.4 — the 2014-15
  oil glut and 2020 COVID super-contango events both push the
  strategy to cash for extended periods
* **Trending-backwardation regimes (2003-08, 2017-19, 2021-22 first
  half)**: Sharpe 0.5-0.8 with low drawdown
* **Persistent-contango regimes (2014-15, 2020 H1)**: Sharpe ~0,
  drawdown bounded by zero exposure (cash position by construction)

## Implementation deviations from EH06 §III

1. **Daily smoothed signal instead of month-end snapshot.** EH06
   computes the roll yield on month-end closes; we use a 21-day
   rolling mean of daily roll yields. The smoothed signal converges
   to the month-end value for slow-moving curves and is more robust
   to the rare days where the front contract gaps relative to the
   back (typical month-end roll-window dynamics).
2. **Long-only.** EH06 §III implements both legs (long backwardation
   / short contango) on a panel; we ship the long leg here and route
   the short-contango leg through `ng_contango_short` to surface
   the contango-specific microstructure assumptions explicitly.
3. **No bid-ask, financing, or short-borrow model.** The bridge
   applies a flat `commission_bps` per leg.
4. **Continuous-contract proxy for F2.** EH06 uses explicit-contract
   data; we use yfinance's `CL2=F` (second-month continuous) as a
   proxy. The proxy preserves the *sign* of the curve slope but
   may slightly bias the *magnitude* near roll boundaries.

None of these change the **economic content** of the EH06 §III rule.

## EH06 abstract excerpt (relevant fragment)

> ... There are at least three sources of return on a fully
> collateralized commodity futures position: the spot return, the
> roll return, and the collateral return. The roll return on a
> fully collateralized position can be substantial, and depends
> critically on the shape of the futures curve ...

## Known replications and follow-ups

* **Bessembinder (1992)** — "Systematic Risk, Hedging Pressure,
  and Risk Premiums in Futures Markets", *Review of Financial
  Studies* 5(4). Empirical decomposition of the curve premium into
  hedging-pressure and macro-risk components; cited by
  `ng_contango_short` for the short-contango microstructure.
* **Levine, Ooi, Richardson, Sasseville (2018)** — "Commodities
  for the Long Run", *Financial Analysts Journal* 74(2). Updates
  the EH06 result through 2016 and confirms the long-run roll-
  yield premium attenuates but persists.
* **KMPV 2018 §IV** — "Carry", *JFE* 127(2). Generalises the curve-
  slope rule into a unified carry framework across asset classes;
  cited by `commodity_curve_carry` (Commit 6).
