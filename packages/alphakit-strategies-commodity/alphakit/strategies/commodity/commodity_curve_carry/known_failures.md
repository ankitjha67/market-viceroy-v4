# Known failure modes — commodity_curve_carry

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

Cross-sectional curve-carry on an 8-commodity panel. Long the
top tercile by roll yield, short the bottom tercile, equal-weighted,
dollar-neutral. Failures cluster around regimes where (a) the
cross-section flattens (no carry to harvest) or (b) curve slopes
flip sharply at regime boundaries.

## 1. Flat-curve regimes (2014-15 commodity glut, 2020 H1 COVID)

When most commodities trade in similar curve regimes (e.g. 2014-15
when the entire commodity panel rolled into contango on the
shale-supply shock + China demand fears, or 2020 H1 when COVID
collapsed demand across the panel), the cross-sectional dispersion
shrinks. The rank book becomes a marginal long-short position with
weak signal — expected Sharpe 0.0-0.3 with elevated turnover.

Expected behaviour for `commodity_curve_carry` in flat-curve
regimes:

* Sharpe of 0.0 to 0.3
* Drawdown 5-10% from peak in the worst flat-curve months
* Turnover ~6-8x annual (vs ~3-4x in normal regimes)

## 2. Sharp curve flips at regime boundaries

When commodity curves flip sharply (e.g. OPEC-cut announcement
Nov 2016 flipping crude from contango to backwardation, or the
2022 H1 energy crisis flipping the energy panel into deep
backwardation), the 21-day smoothed signal lags by ~3 weeks. The
rank book holds the wrong configuration through the flip and
takes 1-2 months to reposition.

Expected drawdown during sharp curve flips: 4-8% over 4-6 weeks.

## 3. Cross-sectional dispersion collapse on broad demand shocks

When all commodities move in the same direction on a single
macro shock (broad reflation 2021, broad risk-off 2008 GFC), the
cross-section becomes degenerate. The strategy is dollar-neutral
by construction so it neither benefits from nor is hurt by the
broad move — but the *opportunity cost* relative to a long-only
commodity book is high. Users wanting to capture macro reflation
should pair this strategy with `commodity_tsmom` (which goes long
the broad trend) or a long-only commodity ETF.

## 4. Single-leg blow-ups

The strategy holds 1/3 long and 1/3 short by default. A single
leg blow-up (e.g. natural gas in February 2021's ERCOT freeze, or
nickel's March 2022 short squeeze on the LME — though nickel is
not in the default panel) can cause the corresponding short leg
to lose 15-25% in 1-2 weeks. With equal weighting (1/3 of the
short book = 1/9 of total notional in any single short leg), the
contribution to portfolio drawdown is bounded by ~3-5%.

Mitigation: tighten `top_quantile` / `bottom_quantile` to 1/4 each
to dilute single-leg exposure; or restrict the universe to
deep-curve commodities (drop NG and HG which have the most
microstructural risk).

## 5. Smaller-universe penalty vs KMPV §IV

The 8-commodity default produces ~30-40% lower long-run Sharpe
than the KMPV §IV 24-commodity panel because of reduced
cross-sectional dispersion. Users wanting the full KMPV result
should override `front_next_map` with an expanded universe and
provide explicit-contract data feeds for the additional commodities
(crude Brent, ULSD, RBOB, copper LME, palladium, livestock,
coffee, sugar, cotton, lumber, etc.). Real-feed support for the
24-commodity panel is deferred to Session 2H.

## 6. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **`wti_backwardation_carry`** (Session 2E sibling, Commit 4) —
  single-asset long-only WTI. Crude is typically the largest
  carry contributor in the panel and lives in the long tail of
  the rank book most months. Expected ρ ≈ 0.4-0.6.
* **`ng_contango_short`** (Session 2E sibling, Commit 5) —
  single-asset short-only NG. NG is typically in the short tail
  during summer-contango months. Expected ρ ≈ 0.3-0.5 in summer,
  lower in winter.
* **`commodity_tsmom`** (Session 2E sibling) — cross-sectional
  momentum on the same panel. Trends and carry align in steep-
  curve regimes; expected ρ ≈ 0.3-0.5.
* **Phase 1 `tsmom_12_1`** (trend family) — different signal,
  different universe; expected ρ ≈ 0.2-0.3.

Master plan §10 cluster-risk bar: ρ > 0.95 triggers deduplication
review. All overlaps are well below the bar.

## 7. Microstructure: continuous-contract roll bias

Same as the single-asset siblings: yfinance's `=F` continuous
contracts are back-adjusted, which preserves close-to-close
returns but introduces a level bias near roll boundaries. The
21-day smoothing absorbs the gap, but in the 5-10 days after each
roll the signal is contaminated by the roll-day artefact.

For real-feed Session 2H benchmarks the cleanest fix is explicit
per-contract data with a documented roll convention.

## 8. Turnover cost for the long-short book

The dollar-neutral construction implies higher turnover than the
single-asset long-only sleeve: a single rank flip moves *two*
legs (the new entry and the displaced commodity). With 8
commodities and 1/3 quantiles → 5-6 legs trade on a typical
month-end rebalance. At 5 bps round-trip and 4-6x annual
turnover, transaction-cost drag is 0.4-0.6% annually — meaningful
relative to the 3-5% expected gross premium.

## Regime performance (reference, from public CTA carry sleeves)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-crisis trending | 2003-01 – 2007-12 | ~0.8 | −5% |
| Crisis flat-curve | 2008-09 – 2009-09 | ~0.1 | −9% |
| Shale-glut flat | 2014-06 – 2016-06 | ~0.2 | −10% |
| COVID dislocation | 2020-03 – 2020-09 | ~0.3 | −7% |
| Post-COVID re-backwardation | 2021-01 – 2022-06 | ~1.0 | −4% |
| 2023 reversal | 2023-01 – 2023-12 | ~0.4 | −6% |

(Reference ranges from public CTA carry sleeves; the in-repo
benchmark is the authoritative source for this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
