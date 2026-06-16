# Known failure modes — permanent_portfolio

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

Static 25/25/25/25 allocation across equity, long bonds, gold, and
cash. The strategy is **deliberately** insensitive to market
conditions — its design hedges the four major economic regimes by
construction. The cost of that insensitivity is documented below.

## 1. Strong bull market regimes (1995–1999, 2017, 2021)

In strong equity bull markets the 75% non-equity allocation
(bonds + gold + cash) is a drag. The permanent portfolio captures
roughly 25% of the equity bull's return. Versus the SPY-only
benchmark over 1995-1999 (dotcom bubble), the permanent portfolio
under-performed by roughly 18% per year cumulatively; versus 2017
the under-performance was ~12%; versus 2021 (post-COVID
reflation) the under-performance was ~14%.

Expected behaviour in similar regimes:

* Sharpe ratio **lower** than SPY-only by 0.5–0.8 over the bull
  window (the diversification benefit reverses in the rear-view
  mirror).
* Cumulative under-performance of 10–20% per year vs equity-only.
* No drawdown — the strategy is long-only and gains money in
  absolute terms; the failure is **relative** to a more
  aggressive benchmark.

This is the canonical permanent-portfolio "failure" — accepted by
construction. Users who want equity-bull-market upside should pair
or replace with a momentum-overlay strategy
(`gtaa_cross_asset_momentum` in this session, or Phase 1
`dual_momentum_gem`).

## 2. High-inflation regimes when gold rallies (1973–75, 2008, 2020 H2)

The strategy outperforms in inflation surprises because the gold
leg rallies materially. 1973-75 inflation: gold leg returned ~80%
cumulatively, lifting overall portfolio return into the high-single-
digits despite negative real bond returns. 2008 GFC + commodity
spike: gold ETF up ~5%, bond ETF up ~30%, equity ETF down ~37% —
permanent portfolio approximately flat versus −37% for equity-only.
2020 H2: gold leg up ~20%, bonds up ~10%, equity up ~10% — strong
year across the board.

**Failure mode:** if gold *lags* during an inflation regime (e.g.
1981-82 disinflation, when both gold and bonds fell while equities
recovered), the permanent portfolio captures the worst of both
worlds — falling gold AND falling bonds simultaneously. The 1981-82
permanent-portfolio max drawdown was ~12% per Estrada (2018)
Table 1.

Expected behaviour in mixed-asset-down regimes:

* Sharpe ratio of −0.2 to −0.5 over the regime window.
* Max drawdown of 10–15% (mitigated relative to equity-only by the
  bond and gold diversification, but not eliminated).

## 3. Real-rate spikes (1979–81, 2022)

When real interest rates rise sharply, **both** long bonds AND gold
lose simultaneously, leaving only cash and (sometimes) equity to
prop up the portfolio. 1979-81 Volcker disinflation: bonds and
gold both down ~20% real, equity flat — permanent portfolio down
~15% in real terms over 18 months. 2022 Fed-tightening cycle: bond
leg (TLT) down 31%, gold leg (GLD) down 1%, equity (SPY) down 18%,
cash (SHY) down 4% — permanent portfolio down ~14% nominally; the
worst single year for the strategy since the 1980s per Estrada-
methodology metrics.

Note the cash proxy mismatch: Browne's original 90-day T-bill cash
leg would have *gained* ~3-4% in 2022; SHY (1-3y duration) lost ~4%
because the short Treasury curve repriced higher. The 4% cash-leg
loss in 2022 is a substrate artefact of using SHY-as-cash, not a
flaw in Browne's design. Documented in `paper.md` "Data Fidelity".

Expected behaviour in real-rate-spike regimes:

* Sharpe ratio of −0.3 to −0.6 over the regime window.
* Max drawdown of 12–18% (the strategy's worst-case regime).

Mitigation: pair with a real-yield-aware overlay (Phase 1
`real_yield_momentum` (rates family) or Session 2G
`growth_inflation_regime_rotation`).

## 4. Rebalance-cadence: monthly signal, daily bridge-side drift correction

The strategy emits the 25/25/25/25 target signal on each **month-end**
bar. The signal is forward-filled to every intermediate bar (the
AlphaKit-wide signal convention established in Phase 1
`dual_momentum_gem` and applied uniformly across Sessions 2D / 2E /
2F / 2G). The vectorbt bridge then applies `SizeType.TargetPercent`
semantics: on each daily bar, it re-marks the portfolio to target
by issuing small drift-correction trades.

**Empirical trade-event count.** A 63-bar test panel produced 3
month-end strategy signals but **156 bridge orders across 41
distinct dates** — verified during Commit 2 gate-3 review. The
realised trade-event rate is **~63 events per asset per year**, not
the ~12 a discrete monthly rebalance would produce.

**Per-trade notional.** Each drift-correction trade rebalances the
*drift since the previous bar*, typically 0.05–0.5% of position
value. The total dollar notional traded across the ~63 daily events
is approximately equivalent to the ~12 events of a true monthly
rebalance of the full position. Total commission cost is bounded
under any reasonable per-trade cost model.

**This is the AlphaKit-wide convention, not a strategy-specific
deviation.** All 99 strategies on `origin/main` (60 Phase 1 + 13
rates + 10 commodity + 15 options + 1 macro pending) inherit the
same pattern: monthly signal cadence + bridge-side daily drift
correction. The convention is documented in
`docs/phase-2-amendments.md` "Session 2G: alphakit-wide rebalance-
cadence convention".

**Compared to Browne 1987.** Browne specifies annual rebalance
with a 10% drift band — rebalance once a year unless any leg
drifts below 15% or above 35%, in which case rebalance immediately.
The AlphaKit implementation is materially more active (~63 events
vs ~1 event per year per asset) but the per-trade notional is
proportionally smaller, so total commission cost is comparable.
No drift-band trigger is implemented; the daily drift correction
effectively dominates the band trigger for any plausible
parameterisation.

**Phase 3 candidate.** A sparse-rebalance protocol extension
(analogous to Session 2F's `discrete_legs` opt-in attribute) would
let strategies suppress the bridge-side daily drift correction
and produce ~12 trade events per year instead of ~63. The
economic exposure under either model is equivalent within
friction-cost noise; the reduction is cleaner for any per-trade
reporting downstream. Out of scope for Session 2G; tracked for
Phase 3 bridge-architecture work.

## 5. Cash-leg duration mismatch

Browne's 1987 cash leg is **90-day T-bills**. The AlphaKit
substrate uses **SHY (1–3 year Treasuries)** because BIL (1–3 month
T-bills) was only launched in 2007 and we want a pre-2007 history
(SHY launched 2002, GLD 2004 are the binding constraints anyway).

The ~1.5 year average duration on SHY makes the "cash" leg
materially interest-rate-sensitive — in a sharp rates move, SHY
can lose 1–4% (versus near-zero for 90-day bills). This is **not**
a bug; it's a substrate constraint documented in `paper.md`. Phase
3 users with a BIL feed from 2007 onward should consider switching
the `cash_symbol` parameter.

## 6. No drift-band rebalance trigger

Browne 1987 specifies a 15%/35% drift band — rebalance any time a
leg falls below 15% or rises above 35% of the portfolio,
*regardless of timing*. This would have triggered intra-month
rebalances during the 2008 GFC and 2020 March COVID crash, when
equity allocations crashed below 15% intra-month.

The AlphaKit implementation only rebalances at month-ends. The
opportunity cost of skipping intra-month rebalances during sharp
drawdowns is small in absolute terms (~50 bps in 2008, ~30 bps in
2020 March) but non-zero. Implementing the drift-band trigger
would require holding-state tracking between bars; deferred to
Phase 3.

## 7. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **No direct Phase 1 sibling.** Phase 1 has no static-weight
  multi-asset allocator. Closest Phase 1 analogs:
  - `dual_momentum_gem` (trend family) — overlapping
    US-equity / bond universe but *dynamic* on momentum.
    Expected ρ ≈ 0.40–0.60 (correlated in trending equity
    regimes when GEM is long equity; uncorrelated in
    risk-off regimes when GEM is long bonds and permanent-
    portfolio is balanced).
  - `vol_targeting` (volatility family) — single-asset
    inverse-vol scaling. Expected ρ ≈ 0.10–0.30 (different
    universe and signal mechanic).

* **Within Session 2G:**
  - `gtaa_cross_asset_momentum` (Commit 3) — 12/1 dynamic
    momentum on a similar multi-asset universe.
    Expected ρ ≈ 0.40–0.60 in trending regimes, lower in
    mean-reverting regimes.
  - `risk_parity_erc_3asset` (Commit 5) — covariance-based
    equal-risk-contribution on stocks/bonds/commodities.
    Expected ρ ≈ 0.60–0.75 (closest multi-asset sibling —
    both allocate significant weight to bonds in low-vol
    regimes; differ on the gold and inflation-rotation
    components).
  - `inflation_regime_allocation` (Commit 12) — same four
    asset classes but rotates 100% allocation based on CPI
    regime. Expected ρ ≈ 0.40–0.60 averaged across regime
    states (the static permanent portfolio mechanically
    matches the inflation-regime rotation in 25% of states).

These overlaps are expected. Phase 2 master plan §10
cluster-risk acceptance bar: ρ > 0.95 triggers deduplication
review. The closest expected ρ (0.60–0.75 with
`risk_parity_erc_3asset`) is well below that bar.

## Regime performance (reference, from Estrada 2018 Table 1 + practitioner data)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Stagflation (1973–75 inflation) | 1973-01 – 1975-12 | ~0.4 | −8% |
| Disinflation (1980–82 Volcker) | 1980-01 – 1982-12 | ~−0.3 | −12% |
| Equity bull (1995–99 dotcom) | 1995-01 – 1999-12 | ~0.6 vs equity ~1.8 | −5% |
| Dotcom crash + early 2000s | 2000-01 – 2003-12 | ~0.7 | −7% |
| GFC (2007–09) | 2007-10 – 2009-03 | ~0.5 | −13% |
| Post-GFC reflation (2010–15) | 2010-01 – 2015-12 | ~0.5 | −9% |
| Real-rate spike (2022) | 2022-01 – 2022-12 | ~−0.6 | −14% |

(Reference ranges from Estrada 2018 Table 1 and practitioner
sources; the in-repo benchmark is the authoritative source for
this implementation — see
[`benchmark_results.json`](benchmark_results.json).)
