# Paper — Natural-Gas Contango Short (Bessembinder 1992 / Erb-Harvey 2006 §III)

## Citations

**Foundational paper:** Bessembinder, H. (1992). **Systematic risk,
hedging pressure, and risk premiums in futures markets.** *Review of
Financial Studies*, 5(4), 637–667.
[https://doi.org/10.1093/rfs/5.4.637](https://doi.org/10.1093/rfs/5.4.637)

Bessembinder (1992) decomposes the commodity-futures risk premium
into hedging-pressure and macro-risk components. The empirical
result: **contangoed commodities exhibit negative excess returns
on long positions, equivalently positive excess returns on short
positions.** The short-side premium is the producer-hedging
pressure that long-only investors pay for taking the storage side
of the trade.

**Primary methodology:** Erb, C. B. & Harvey, C. R. (2006). **The
strategic and tactical value of commodity futures.** *Financial
Analysts Journal*, 62(2), 69–97.
[https://doi.org/10.2469/faj.v62.n2.4084](https://doi.org/10.2469/faj.v62.n2.4084)

Section III ("The Term Structure Story") implements both legs of
the curve premium — long backwardation, short contango — on the
1982-2004 commodity panel. The most-contangoed leg (natural gas)
posts the largest contango short-side premium in the panel.

BibTeX entries `bessembinder1992` and `erbHarvey2006` are
registered in `docs/papers/phase-2.bib`.

## Why NG specifically

Natural gas exhibits the most pronounced and persistent contango
in the commodity panel for two structural reasons:

1. **Seasonal storage cycle.** Gas is *injected* into storage from
   April to October (cooling-demand months → low spot demand) and
   *withdrawn* from November to March (heating-demand months →
   high spot demand). The summer storage-build phase pushes the
   front contract below the next contract by 5-15% — deep, stable
   contango from May through September almost every year.
2. **Storage-cost drag.** NG is expensive to store (liquefaction +
   tank rental + boil-off + injection-withdrawal fees), so the
   no-arbitrage upper bound on the curve slope is large. Contango
   can run very wide before storage arbitrageurs are incentivised
   to flatten it.

The producer-hedging-pressure premium documented in Bessembinder
(1992) is therefore concentrated in NG: producers consistently
hedge-sell forward contracts to lock in revenue, paying the
short-side premium to speculators who take the other side.

## Differentiation from sibling carry strategies

* **`wti_backwardation_carry`** (Session 2E sibling, Commit 4) —
  long-only mirror trade on WTI (the canonical-most-backwardated
  commodity). Different commodity, opposite curve regime,
  asymmetric trading rule. Expected ρ with `ng_contango_short`
  ≈ 0.0-0.2 (the curves trade different physical regimes).
* **`commodity_curve_carry`** (Session 2E sibling, Commit 6) —
  cross-sectional rank-based carry on the broader 8-commodity
  panel (KMPV 2018 §IV). NG typically appears in the *short* tail
  of the rank book during summer months, so this strategy and
  `commodity_curve_carry` overlap on the NG short leg. Expected
  ρ ≈ 0.3-0.5 in summer-contango months, lower in winter.
* **Trend-family `tsmom_12_1`** (Phase 1) — different signal
  entirely (trailing returns, not curve slope); ρ ≈ 0.0-0.2.

## Curve-slope signal

For each trading day *t*::

    roll_yield(t) = (F1(t) - F2(t)) / F2(t)

where ``F1`` is the front-month NG contract and ``F2`` is the
next-listed-month contract. Negative = contango (curve slopes
upward); positive = backwardation.

The raw daily series is noisy. We smooth with a 21-day rolling
mean before the signal, mirroring `wti_backwardation_carry`'s
smoothing window for symmetry between the long-backwardation and
short-contango sub-strategies.

| Parameter | EH06 §III value | AlphaKit default | Notes |
|---|---|---|---|
| Curve metric | (F1 − F2) / F2 | (F1 − F2) / F2 | identical |
| Smoothing | end-of-month observation | 21-day rolling mean | EH06 uses month-end snapshots; we smooth daily |
| Signal threshold | < 0 short | < 0 short, else flat | short-only by design |
| Rebalance | monthly | daily | smoother daily evaluation |

## Trading rule

Short-only — the asymmetric mirror of `wti_backwardation_carry`:

* smoothed roll yield < `-contango_threshold` → **−1** (short the
  front-month NG contract)
* otherwise → **0** (cash)

We deliberately do **not** *buy* backwardation here. The
long-backwardation NG trade has a separate microstructure (winter
heating-demand season, weather-dependent) that warrants its own
strategy or a tactical overlay; we keep it out of this strategy
to surface the canonical contango short cleanly.

## In-sample period (Bessembinder 1992 / Erb-Harvey §III)

* Bessembinder data: 1967-1989 commodity-futures panel (NG futures
  began trading on NYMEX in April 1990, so Bessembinder's NG
  evidence is implicit through the broader contango-short result
  on storable commodities).
* Erb-Harvey data: 1982-2004; NG futures included from 1990 onwards.
  The NG contango-short sub-strategy reports a Sharpe of ~0.7 over
  1990-2004 (Table III).
* OOS update (Levine et al. 2018): 2005-2016 NG contango short
  Sharpe ~0.4 — meaningfully degraded by the 2009-2010 storage
  glut and the 2014-2015 oil/gas correlation regime.

For the AlphaKit default we expect:

* **Long-window OOS Sharpe (2005-2025)**: 0.2-0.5 — the persistent-
  contango regimes still earn the short premium but several
  inversion events (2014 polar vortex, 2022 H1 European energy
  crisis) cause large short-squeezes.
* **Summer-contango months (May-September most years)**: Sharpe
  0.7-1.2 with low drawdown.
* **Winter-backwardation months (typically November-March)**:
  Sharpe ~0 (strategy is in cash by construction).

## Implementation deviations from EH06 §III

1. **Daily smoothed signal instead of month-end snapshot.** Same
   rationale as `wti_backwardation_carry`: 21-day rolling mean is
   more robust to roll-day jitter than a single end-of-month
   observation.
2. **Short-only.** EH06 §III implements both legs (long
   backwardation / short contango) on a panel; we ship the
   short-contango leg here as a NG-specific expression, with the
   long-backwardation leg in `wti_backwardation_carry`.
3. **No bid-ask, financing, or short-borrow model.** The bridge
   applies a flat `commission_bps` per leg. NG futures shorts are
   mechanically trivial (no borrow / locate) but spreads can widen
   sharply in extreme weather events; users running on real-feed
   data should consider a regime-dependent commission overlay.
4. **Continuous-contract proxy for F2.** Same as
   `wti_backwardation_carry`: yfinance's `NG2=F` is used as a
   next-month proxy. Preserves the *sign* of the curve slope but
   may bias the *magnitude* near roll boundaries.

## Bessembinder (1992) abstract excerpt

> ... I find evidence consistent with a residual hedging-pressure
> effect, suggesting that the futures risk premium is partially
> determined by the net hedging position of the commercial
> traders ... When net hedgers are short, the futures risk premium
> is positive (i.e. long futures earn excess returns); when net
> hedgers are long, the futures risk premium is negative (i.e.
> short futures earn excess returns) ...

In NG markets, *producers* (gas drillers / pipeline operators)
are the net short hedgers — they sell forward contracts to lock in
revenue. By Bessembinder's framework this implies a **positive
short-side premium**: speculators who take the long side of
producer hedges earn excess returns on long positions (which is
the long-backwardation case) but in NG markets the producer-hedge
flow is dominated by the seasonal storage-build cycle that *also*
pushes the curve into contango — the result is a negative roll
yield that long-only investors *pay* and short-side speculators
*harvest*. The two effects align in NG specifically.

## Known replications and follow-ups

* **Hong & Yogo (2012)** — "What Does Futures Market Interest Tell
  Us about the Macroeconomy and Asset Prices?", JFE 105(3).
  Decomposes commodity-curve-position dynamics; supports the
  hedging-pressure interpretation.
* **Levine, Ooi, Richardson, Sasseville (2018)** — "Commodities
  for the Long Run", FAJ 74(2). Updates the EH06 contango-short
  result through 2016 and confirms the NG sub-strategy still
  posts a positive Sharpe with degraded magnitude.
* **De Roon, Nijman, Veld (2000)** — "Hedging Pressure Effects in
  Futures Markets", JF 55(3). Cited by `cot_speculator_position`
  (Commit 7) for a complementary speculator-positioning signal.
