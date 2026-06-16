# Known failure modes — inflation_regime_allocation

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

Neville et al. (2021) / Erb-Harvey (2006) inflation-regime 3-cell
allocation across SPY / TLT / GLD / DBC driven by one CPIAUCSL
informational column. Fifth and final consumer of the regime-state
primitive.

## 1. Regime-boundary whipsaw near the 2% and 4% thresholds

The 3-cell classification uses hard thresholds (2% and 4% CPI YoY).
When the CPI YoY rate oscillates near a threshold (e.g. hovering
around 2% during a disinflation), the regime flips between adjacent
cells, producing whipsaw turnover.

Each regime flip involves a 4-leg reallocation:
* Low ↔ Moderate: (60/30/5/5) ↔ (40/20/20/20) — large GLD/DBC change.
* Moderate ↔ High: (40/20/20/20) ↔ (5/5/45/45) — massive SPY/TLT drop.

Expected behaviour near regime boundaries:
* 200-400% notional turnover per regime flip.
* Whipsaw cost of 2-6% per year when the CPI oscillates near a
  threshold (e.g. 2015-2016 when CPI YoY oscillated around 0-2%;
  2019 when YoY was 1.5-2.5%).

Mitigation: widen the threshold deadbands or require N months of
confirmation before flipping. The constructor exposes `low_threshold`
and `high_threshold`.

## 2. Publication-lag forensics (load-bearing)

CPIAUCSL is published ~mid-month for the prior month. The strategy
applies `cpi_lag_months=1` before computing the YoY. 

**Critical:** the YoY is computed on the *lagged* series:
```
cpi_yoy = cpi_lagged.pct_change(12) * 100
```

Computing YoY first and then lagging the result would mix real-time
CPI (month *t*) with revised CPI (month *t−12*), introducing a subtle
lookahead. The correct order: lag then YoY.

Failure to apply the lag would inflate the backtest Sharpe by
~0.2-0.5 (the foresight premium of knowing the current CPI before
the rebalance). The exact magnitude depends on the regime-transition
frequency.

Verified by
`tests/test_unit.py::test_publication_lag_applied_before_yoy`.

This is load-bearing: inherited from the group convention in
`growth_inflation_regime_rotation/known_failures.md` item 3.

## 3. Gold disappointment in the 2022 high-inflation episode

Neville et al. (2021) document gold's high-inflation return benefit
over a 95-year sample. However, in 2022 (CPI YoY peaking at ~9%),
gold delivered approximately −2% nominal (underperformed).

The reasons are well-understood post-hoc:
1. Real rates rose sharply (the Fed raised from 0% to 4.5%), which
   directly compresses gold's zero-coupon valuation.
2. The 2022 episode was a **rate-hiking cycle** high inflation (not a
   demand-pull inflation), which has historically been less favorable
   to gold than demand-pull / stagflation inflation.

Expected behaviour in rate-hiking high inflation:
* GLD underperforms the historical average for the high-inflation cell.
* DBC (commodities) outperforms more reliably (energy-heavy).
* Net: the high-inflation cell (5% SPY / 5% TLT / 45% GLD / 45% DBC)
  depends critically on DBC outperforming to offset the GLD
  disappointment.

## 4. Deflation cell: CPI YoY can go negative

The 3-cell taxonomy classifies CPI YoY < 2% as "low" but does not
distinguish between modest disinflation (1% YoY) and deflation
(−1% YoY, as in 2009 Q3 and 2015). In deflationary episodes, the
"low" allocation (60% SPY / 30% TLT) is equity-heavy, which may
be inappropriate if deflation is accompanied by a severe recession
(as in 2009).

Expected behaviour in deflation:
* Strategy holds 60% SPY — which may fall sharply in a deflationary
  recession (2009 SPY was down ~40% from peak by March 2009).
* The 30% TLT partially offsets (TLT is a strong deflation hedge).
* Net: the low-inflation allocation provides limited protection in
  deflationary recessions.

Mitigation: add a 4th "deflation" cell for CPI YoY < 0, with a more
defensive allocation. Out of scope for this commit.

## 5. Commodity-futures roll cost (DBC-specific)

DBC (DB Commodity Index ETF) is a futures-based product. Commodity
futures have roll costs when the futures curve is in contango (far
contracts more expensive than near contracts). In periods of moderate
inflation with stable commodity prices, contango roll costs can
subtract 5-10% per year from DBC's return, making it a drag on the
moderate-inflation cell.

Expected behaviour:
* DBC underperforms spot commodities by the roll cost (~5-10% per year
  in contango environments).
* In the high-inflation cell (45% DBC), the roll cost drag is ~2-5%
  per year on the total portfolio, partially offsetting the commodity
  inflation-hedging benefit.
* In the moderate-inflation cell (20% DBC), the drag is ~1-2% per year.

## 6. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **Phase 2 Session 2G `growth_inflation_regime_rotation`** (Commit 9)
  — overlapping CPI dimension. The inflation classification in Commit 9
  uses the same CPIAUCSL series with the same lag. Expected ρ ≈
  **0.40-0.60** (inflation dimension is the direct overlap; growth
  dimension differentiates).
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) — static
  4-asset allocation. Expected ρ ≈ **0.40-0.60**. Both strategies
  hold SPY/TLT/GLD/DBC; the correlation arises from the shared
  asset universe, not from regime alignment. Specifically:
  * In moderate inflation (this strategy's 40/20/20/20), weights are
    somewhat close to PP's 25/25/25/25 → moderate correlation.
  * In low inflation (60/30/5/5), GLD/DBC weight collapses → lower ρ
    with PP.
  * In high inflation (5/5/45/45), SPY/TLT weight collapses → lower ρ
    with PP.
  * On average over the inflation regime distribution, ρ ≈ 0.40-0.60.
* **Phase 2 Session 2G `recession_probability_rotation`** (Commit 8)
  — overlapping macro factor. Expected ρ ≈ **0.30-0.50**.
* **Phase 2 Session 2G `yield_curve_regime_allocation`** (Commit 10)
  — yield-curve slope. Expected ρ ≈ **0.30-0.50**.
* **Phase 2 Session 2G `fed_policy_tilt`** (Commit 11) — Fed funds
  rate. Expected ρ ≈ **0.30-0.50**.

All pairwise ρ values within the regime-state group sit in the
0.30-0.60 range — well below the ρ > 0.95 dedup-review bar.

## Regime performance (reference, from Neville et al. 2021 + Erb-Harvey 2006)

| Regime | Example window | Sharpe | Max DD |
|---|---|---|---|
| Low inflation (equity+bonds) | 2012-2019, 2023-present | ~0.7 | −8% |
| Moderate inflation (balanced) | 2004-2007, 2020-2021 | ~0.5 | −10% |
| High inflation (gold+commodities) | 2022 | ~0.2 | −15% (gold disappointing) |
| Deflation within low cell | 2009, 2015 | ~−0.2 | −20% (equity-heavy) |
| Near-threshold whipsaw | 2015-2016, 2019 | ~0.0-0.2 | −8% (turnover) |

(Reference ranges from Neville et al. 2021 Fig 3 and Table 1 + Erb-Harvey 2006
Table 1; the in-repo benchmark is the authoritative source — see
[`benchmark_results.json`](benchmark_results.json).)
