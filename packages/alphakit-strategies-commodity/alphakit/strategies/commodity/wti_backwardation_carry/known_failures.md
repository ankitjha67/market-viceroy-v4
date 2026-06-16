# Known failure modes — wti_backwardation_carry

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

Long-only WTI carry on the front-vs-next-month curve slope. The
strategy is in cash whenever the curve is contangoed, so it cannot
*lose* directly during contango — but its **opportunity cost** in
contango regimes is significant, and the once-in-a-decade
super-contango events (2014-15, 2020 H1) are the dominant
performance drag on the long-only book.

## 1. Persistent-contango regimes (2014-15 oil glut, 2020 H1 COVID)

Two episodes pushed the WTI curve into deep-and-persistent contango
that lasted 18-24 months each:

* **2014-2015**: OPEC declined to cut production into a US shale-
  oil supply surge. WTI front-month dropped from $107 (June 2014)
  to $26 (Feb 2016); the curve rolled into deep contango (front
  $4-6 below 6-month-out).
* **2020 H1**: COVID demand collapse + Saudi-Russia price war.
  WTI futures briefly traded **negative** on 20 April 2020 (May
  contract settlement); curve was in super-contango for ~6 months
  through Sep 2020.

Expected behaviour for `wti_backwardation_carry` in similar regimes:

* Sharpe of ~0.0 (strategy is in cash)
* Drawdown: 0% direct, but very high opportunity cost vs a long-only
  buy-and-hold or a short-contango book
* Users wanting exposure to contango regimes should pair this with
  `ng_contango_short` and/or `commodity_curve_carry` (which captures
  the rank-relative carry premium in both regimes)

## 2. Sharp curve flips at regime boundaries

When the curve flips from contango → backwardation (or vice versa),
the 21-day smoothed signal lags by ~3 weeks. The strategy will
miss the first 2-3 weeks of a new backwardation regime (entry
delay) and stay long for ~3 weeks into a new contango regime
(exit delay). In OPEC-cut announcements (e.g. Nov 2016, Dec 2018,
Apr 2020 G20 deal) the curve flip can be very fast — 1-2 weeks —
and the smoothed signal is consistently late.

Mitigation: tune `smoothing_days` lower (e.g. 5-10 days) for users
who want faster regime detection, at the cost of more signal
flips in noisy curve regimes.

## 3. Single-day price gaps at the front-month roll

WTI futures roll on the 25th of the prior month (or 4th business
day before the 25th, technically). On the roll date the front-
contract series jumps from one expiry to the next. yfinance's
`CL=F` continuous series is back-adjusted to preserve close-to-
close returns but the *level* gap is preserved as a step in the
underlying contract change. The 21-day smoothing window absorbs
the gap, but in the 5-10 days *immediately* after a roll the
smoothed signal is contaminated by the roll-day noise. This is
a microstructure artefact, not an economic signal.

## 4. F2 proxy bias

We use yfinance's `CL2=F` (second-month continuous) as a proxy for
the next-listed-month contract. The proxy preserves the *sign* of
the curve slope (backwardation/contango) but the *magnitude* is
biased near roll boundaries because `CL2=F` rolls one expiry later
than `CL=F`. For real-feed Session 2H benchmarks the cleanest
fix is to use explicit per-contract data (CL_2025M, CL_2025N,
etc.) with a documented roll convention.

## 5. Negative front-month price (April 2020)

On 20 April 2020 the May 2020 WTI contract settled at **−$37.63**.
The strategy's input validation rejects non-positive prices with
`ValueError("prices must be strictly positive")`, which is correct
for a generic price series but fails on this specific historical
day. Users running on real WTI data must either:

* Pre-filter the negative-price day from the input series, **or**
* Switch the front contract to the next-listed-month immediately
  ahead of the negative-price settlement (i.e. roll early)

This is documented as a *data-quality* known failure rather than a
strategy logic failure — the EH06 §III rule was never tested on
negative-price regimes because no commodity futures had ever
settled negative before April 2020.

## 6. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **`commodity_curve_carry`** (Session 2E sibling, Commit 6) —
  cross-sectional rank-based carry on the broader 8-commodity
  panel (KMPV 2018 §IV). Crude is typically the largest carry
  contributor in the panel, so the WTI single-asset book is
  highly loaded onto the cross-sectional signal. Expected
  ρ ≈ 0.4-0.6.
* **`ng_contango_short`** — different commodity (NG vs WTI),
  different curve regime (NG is structurally contangoed in summer
  cooling-demand season, backwardated in winter; WTI is more
  cyclical). Expected ρ ≈ 0.0-0.2.
* **`commodity_tsmom`** (Session 2E sibling) — different signal
  (trailing returns, not curve). When momentum and carry align
  (steep-curve trending regimes), ρ ≈ 0.3-0.5; otherwise
  ρ ≈ 0.1-0.3.
* **Trend-family `tsmom_12_1`** (Phase 1) — different signal,
  different universe; ρ ≈ 0.1-0.3.

Master plan §10 cluster-risk bar: ρ > 0.95 triggers deduplication
review. The `commodity_curve_carry` overlap (ρ ≈ 0.4-0.6) is well
below the bar — the WTI single-asset expression is materially
different from the cross-sectional rank, and both ship.

## 7. Long-only opportunity cost vs the panel

By construction `wti_backwardation_carry` is in cash whenever
crude is contangoed (typically 30-40% of trading days over a
20-year sample). Users should view this strategy as a *crude-
carry sleeve* that complements other commodity exposures, not a
standalone return engine. The Sharpe in cash periods is
mechanically zero, dragging the long-window Sharpe to the 0.2-0.4
range — meaningfully below the panel-wide cross-sectional carry
book.

## Regime performance (reference, from public commodity-overlay sleeves)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-shale backwardation | 2003-2008 | ~0.7 | −5% |
| Shale-supply contango | 2014-2016 | ~0.0 (cash) | 0% (opportunity cost) |
| Post-OPEC-cut backwardation | 2017-2019 | ~0.5 | −7% |
| COVID super-contango | 2020 H1 | ~0.0 (cash) | 0% |
| Post-COVID re-backwardation | 2021-2022 H1 | ~1.0 | −4% |
| Late-2022 demand-fear contango | 2022-12 – 2023-12 | ~0.0 (cash) | 0% |

(Reference ranges from public commodity-overlay sleeves; the
in-repo benchmark is the authoritative source for this
implementation — see [`benchmark_results.json`](benchmark_results.json).)
