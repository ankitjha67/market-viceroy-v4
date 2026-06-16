# Paper — Vigilant Asset Allocation (Keller-Keuning 2017, 5-ETF variant)

## Citations

**Initial inspiration:** Keller, W. J. & Keuning, J. W. (2014).
**A Century of Generalized Momentum: From Flexible Asset
Allocations (FAA) to Elastic Asset Allocation (EAA).** SSRN
Working Paper 2543979.
[https://doi.org/10.2139/ssrn.2543979](https://doi.org/10.2139/ssrn.2543979)

**Primary methodology:** Keller, W. J. & Keuning, J. W. (2017).
**Breadth Momentum and the Canary Universe: Defensive Asset
Allocation (DAA).** SSRN Working Paper 3002624.
[https://doi.org/10.2139/ssrn.3002624](https://doi.org/10.2139/ssrn.3002624)

(Published variously as "Breadth Momentum and Vigilant Asset
Allocation" — the SSRN title later updated to reference DAA which
shares the same canary-momentum mechanic. The 2017 paper is the
canonical reference for the VAA / DAA breadth-momentum framework.)

BibTeX entries are registered in `docs/papers/phase-2.bib` under
`kellerKeuning2014generalized` (foundational) and
`kellerKeuning2017breadth` (primary).

## Why two papers

Keller-Keuning 2014 specifies the **generalized-momentum
aggregator** — the weighted multi-horizon score that aggregates
1-, 3-, 6-, and 12-month returns into a single number. The 2014
paper documents that the weighted aggregator is more reactive than
plain 12-month momentum (the 1-month weight dominates at
``W = 12·r_1 + 4·r_3 + 2·r_6 + r_12``) while preserving the
long-run trend signal. EAA (2014) layers a crash-protection rule
on top of this aggregator that is the precursor to VAA's canary
gate.

Keller-Keuning 2017 adds the **breadth-momentum gate** that is the
load-bearing innovation of VAA over plain TSMOM. The gate uses a
canary universe (typically the same as the offensive universe) to
decide whether the portfolio is risk-on or risk-off:

> If *any* canary asset has a non-positive 13612W score, the
> portfolio goes 100% defensive. Otherwise it allocates to the
> top-N offensive assets by score.

This any-negative breadth filter is materially more conservative
than a majority-vote or aggregate-score filter — a single weak
asset class is sufficient to flip the portfolio to defensive,
producing strong crash protection at the cost of higher whipsaw
risk during indecisive markets.

Implementation replicates the 2017 paper's VAA-G4 specification
(4 offensive + 3 defensive) with one substrate simplification:
the 3-asset defensive bucket is collapsed to a single SHY leg
(see "Implementation deviations" below).

## Differentiation from sibling strategies

* **Phase 1 `dual_momentum_gem`** (trend family, Antonacci 2014) —
  closest cluster sibling. Both use discrete momentum-based
  rotation with a defensive cash-bucket fallback. Three
  load-bearing differentiations:
    1. **Score formulation.** `dual_momentum_gem` uses a single
       12-month total return; VAA aggregates 4 lookback horizons
       via the 13612W weighted score. The 13612W aggregator is
       materially more reactive — VAA flips into defensive earlier
       in a developing drawdown.
    2. **Universe and bucket structure.** `dual_momentum_gem` uses
       a 3-asset offensive (US / Intl / bonds) with absolute-
       momentum filter on US-vs-risk-free; VAA uses a 4-asset
       offensive (SPY/EFA/EEM/AGG) with the canary gate on *all
       four* assets (any-negative → defensive).
    3. **Defensive bucket.** `dual_momentum_gem` falls back to AGG
       (intermediate Treasuries with credit); this VAA variant
       falls back to SHY (short Treasuries, cleaner cash proxy).
  Expected ρ ≈ **0.40–0.60** (correlated direction in clear
  regimes; uncorrelated during transitional periods when the
  more-reactive 13612W and the 12-month signal disagree).
* **Phase 2 Session 2G `gtaa_cross_asset_momentum`** (Commit 3,
  AMP 2013 §V) — same broad-asset universe theme but continuous-
  vol-scaled long-short weights instead of discrete top-1 /
  defensive rotation. Expected ρ ≈ 0.30–0.50 in clean trending
  regimes; lower otherwise.
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  static 25/25/25/25 allocator with no rotation logic. Expected
  ρ ≈ 0.20–0.40 (static-vs-tactical philosophy).
* **Phase 1 `tsmom_12_1`** (trend family, MOP 2012) — single-
  horizon vol-scaled TSMOM. Different shape entirely. Expected
  ρ ≈ 0.20–0.40.

## Published rules (Keller-Keuning 2017 VAA-G4, 5-ETF variant)

For each month-end *t*:

1. Compute 4 monthly returns for each of the 5 ETFs:

       r_1(a)  = price(a, t) / price(a, t-1m)  - 1
       r_3(a)  = price(a, t) / price(a, t-3m)  - 1
       r_6(a)  = price(a, t) / price(a, t-6m)  - 1
       r_12(a) = price(a, t) / price(a, t-12m) - 1

2. Compute the 13612W weighted momentum score:

       W(a) = 12 · r_1(a) + 4 · r_3(a) + 2 · r_6(a) + r_12(a)

   The 1-month weight (12 / 19 of the total = ~63%) dominates the
   score — VAA reacts faster than a plain 12-month signal.

3. Breadth-momentum gate (canary check):
   - If ANY of the 4 offensive assets has ``W(a) ≤ 0``: portfolio
     is **risk-off**.
   - Otherwise (ALL 4 offensive assets have ``W(a) > 0``):
     portfolio is **risk-on**.

4. Allocation:
   - Risk-on: weight = 1.0 on the offensive asset with the highest
     13612W score; weight = 0.0 on all others.
   - Risk-off: weight = 1.0 on SHY; weight = 0.0 on all four
     offensive assets.

5. Hold one month, recompute at the next month-end.

| Parameter | Keller-Keuning 2017 VAA-G4 | AlphaKit default | Notes |
|---|---|---|---|
| Score formulation | 13612W | 13612W | identical |
| Score weights | (12, 4, 2, 1) | (12.0, 4.0, 2.0, 1.0) | identical |
| Lookbacks | (1, 3, 6, 12) months | (1, 3, 6, 12) | identical |
| Offensive universe | SPY, VEA, VWO, BND | SPY, EFA, EEM, AGG | symbol-class equivalents |
| Defensive universe | LQD, IEF, SHY (top-1 by 13612W) | SHY only | substrate simplification |
| Allocation | Top-1 of offensive / top-1 of defensive | Top-1 of offensive / SHY | identical for offensive |
| Rebalance | Monthly | Monthly | identical |

### Why the substrate simplifications

* **VEA → EFA, VWO → EEM, BND → AGG.** All three are direct ETF-
  class equivalents (developed international / emerging markets /
  US aggregate bonds). VEA / VWO / BND launched later than EFA /
  EEM / AGG; using the older AlphaKit-standard symbols extends the
  available history.
* **3-asset defensive collapsed to 1 leg.** The paper's
  defensive bucket (LQD / IEF / SHY) selects the top-1 by 13612W
  among the 3 defensive ETFs. The 5-ETF spec in the Session 2G
  plan forces a simplification — SHY is chosen as the cleanest
  cash proxy (1-3y Treasuries). The trade-off: in risk-off regimes
  the strategy cannot benefit from credit-spread tightening (LQD
  out-performing SHY) or duration extension (IEF out-performing
  SHY). Documented in `known_failures.md` item 3.

## Data Fidelity

* **Substrate:** daily closing prices from yfinance for 5 ETFs.
  All five have inception dates before 2005: SPY (1993), EFA
  (2001), EEM (2003), AGG (2003), SHY (2002). Continuous panel
  from 2005 onward.
* **No transaction costs in synthetic fixture.** The vectorbt
  bridge applies a configurable flat ``commission_bps`` per
  rebalance leg. The in-repo benchmark in
  ``benchmark_results.json`` reports headline metrics at
  ``commission_bps = 5.0``.
* **Rebalance cadence:** monthly target signal, daily bridge-side
  drift correction (AlphaKit-wide convention; see Session 2G
  amendment "alphakit-wide rebalance-cadence convention" in
  ``docs/phase-2-amendments.md``).
* **Discrete top-1 picking** means trades are *concentrated* at
  rotation events (full 100% swap from one ETF to another). When
  the top-1 offensive flips between SPY and EFA, the bridge fires
  a 200%-notional turnover trade — twice the typical drift-
  correction turnover. Expected to occur 0-3 times per year on
  realistic data.

## Expected Sharpe range

`0.4 – 0.7 OOS` (Keller-Keuning 2017 Table 4 reports Sharpe ≈
0.65 for VAA-G4 on 1971-2017 US-data sample with the 3-asset
defensive bucket; the 5-ETF collapsed-defensive variant is
expected to be marginally lower because of the lost defensive-
bucket flexibility). The lower bound of 0.4 accounts for the
collapsed defensive and the shorter EM-equity data history
(EEM only from 2003); the upper bound of 0.7 reflects Keller-
Keuning's reported range across in-sample and out-of-sample
windows.

## Implementation deviations from Keller-Keuning 2017 VAA-G4

1. **3-asset defensive bucket collapsed to 1 leg (SHY only).**
   See "Why the substrate simplifications" above. Quantitatively,
   the lost flexibility is small in absolute terms (LQD vs SHY
   spread is typically 1-3% per year; IEF vs SHY spread is
   typically 0.5-2%). The simplification is preserved as a
   constructor parameter — Phase 3 users can re-introduce the
   3-asset defensive by composing this strategy with a separate
   defensive-bucket picker.
2. **Symbol substitutions** (VEA → EFA, VWO → EEM, BND → AGG).
   Direct ETF-class equivalents with longer histories on yfinance.
3. **No bid-ask, financing, or short-borrow model.** Long-only,
   single-asset 100%-allocation; no shorting, no leverage. The
   bridge applies a flat ``commission_bps`` per rotation event.

None of these change the *sign* of any allocation or the
breadth-momentum gate logic; they affect only the defensive-
bucket diversification within risk-off regimes.

## Known replications and follow-ups

* **Keller, W. J. (2018)** — *Defensive Asset Allocation (DAA):
  Aggressive Protection with a Concentrated Canary*, SSRN
  3221837. Extends VAA with a *separate* canary universe (BND +
  VWO) rather than reusing the offensive bucket as canary — more
  conservative crash protection at the cost of higher whipsaw.
* **Keller, W. J. & Keuning, J. W. (2018)** — *Protective Asset
  Allocation (PAA): A Simple Momentum Strategy*, SSRN 2759734.
  Sister strategy that uses a different protective gate (top-N of
  offensive scaled by breadth count) rather than the binary
  canary-any-negative gate.
* **Faber, M. (2007)** — *A Quantitative Approach to Tactical
  Asset Allocation*, JoWM Spring 2007. The foundational tactical-
  asset-allocation paper that VAA / DAA / PAA all build on.
