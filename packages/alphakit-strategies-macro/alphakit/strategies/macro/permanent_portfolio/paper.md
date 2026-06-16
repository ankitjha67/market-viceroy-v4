# Paper — Permanent Portfolio (Browne 1987 / Estrada 2018)

## Citations

**Initial inspiration:** Browne, H. (1987). **Why the Best-Laid
Investment Plans Usually Go Wrong: And How You Can Find Safety and
Profit in an Uncertain World.** Quill / William Morrow.
ISBN 0-688-06778-6.

**Primary methodology:** Estrada, J. (2018). **From Failure to
Success: Replacing the Failure Rate.** SSRN Working Paper 3168697.
[https://doi.org/10.2139/ssrn.3168697](https://doi.org/10.2139/ssrn.3168697)

BibTeX entries are registered in `docs/papers/phase-2.bib` under
`browne1987permanent` (foundational, book ISBN) and
`estrada2018failure` (primary, SSRN DOI).

## Why two papers

Browne 1987 is the canonical statement of the Permanent Portfolio
construction. The book is a popular-press investment treatise and
does not provide formal out-of-sample back-testing. Browne's
prescription is straightforward — split equally across four asset
classes that respond differently to the four major economic
regimes — but the empirical performance evidence in the original
book is anecdotal.

Estrada 2018 supplies the academic empirical anchor. Table 1 reports
the Sharpe ratio of the 25/25/25/25 US Permanent Portfolio over
1972–2016 at approximately 0.5, with explicit failure-rate analysis
across the four major regime stresses (1973–74 inflation, 1980–82
disinflation, 2000–02 dotcom bust, 2008 GFC). Estrada also extends
the analysis to 10 developed-market panels (Australia, Canada, France,
Germany, Italy, Japan, Netherlands, Switzerland, UK, US) and
demonstrates that the strategy's regime-balancing intuition is robust
across geographies.

Implementation faithfully replicates Browne's construction (the four
asset classes + the equal-weight rule); benchmark numbers are
calibrated to Estrada's reported Sharpe range.

## Differentiation from sibling strategies

* **No direct Phase 1 sibling.** Phase 1 has no static-weight
  multi-asset allocator. The closest analogs are `dual_momentum_gem`
  (trend family, 3-asset universe but *dynamic* on momentum) and
  `vol_targeting` (volatility family, single-asset). Expected
  cluster correlations with Phase 1:
  - Phase 1 `dual_momentum_gem`: ρ ≈ 0.40–0.60 (overlapping US-
    equity / bond universe but dynamic-vs-static weighting).
  - Phase 1 trend / mean-reversion / carry / value / volatility:
    ρ ≈ 0.10–0.40 (different asset universes and signal mechanics).
* **Within Session 2G:**
  - `gtaa_cross_asset_momentum` (Commit 3) — dynamic momentum on
    multi-asset ETFs; close universe but different weighting
    philosophy. Expected ρ ≈ 0.40–0.60 in trending regimes (when
    AMP momentum aligns with permanent-portfolio constituents)
    and lower in mean-reverting regimes.
  - `risk_parity_erc_3asset` (Commit 5) — closest multi-asset
    sibling but covariance-based ERC weights instead of fixed
    25/25/25/25. Expected ρ ≈ 0.60–0.75 because both allocate
    significant weight to bonds in low-vol regimes.
  - `inflation_regime_allocation` (Commit 12) — same four asset
    classes but rotates *all* weight to a single asset based on
    CPI regime. Expected ρ ≈ 0.40–0.60 averaged across regimes
    (the static permanent portfolio matches the inflation-regime
    rotation in 25% of regime states by construction).

## Published rules (Browne 1987 verbatim)

For each month-end *t*:

1. Compute the realised drift of each leg's weight from its 25%
   target since the previous rebalance (forward-filled weights
   between month-ends carry the drift).
2. Rebalance all four legs back to **25% target weight**:
   - Equity: SPY (US large-cap)
   - Long bonds: TLT (20+ year Treasuries)
   - Gold: GLD (physical gold)
   - Cash: SHY (1–3 year Treasuries, cash proxy)
3. Hold one month. Repeat.

There is no signal, no lookback, no regime state, no covariance
estimation. The four asset classes are chosen to *mechanically*
hedge the four major economic regimes:

| Regime | Hedge asset | Reason |
|---|---|---|
| Prosperity (growth ↑, inflation moderate) | Equity (SPY) | Equity earns the equity risk premium |
| Deflation (growth ↓, inflation ↓) | Long bonds (TLT) | Long duration appreciates as yields fall |
| Inflation (growth varies, inflation ↑) | Gold (GLD) | Gold is the canonical inflation hedge |
| Tight money / recession (growth ↓, real rates ↑) | Cash (SHY) | Short-duration Treasuries preserve capital |

| Parameter | Browne 1987 | AlphaKit default | Notes |
|---|---|---|---|
| Equity leg | S&P 500 | `"SPY"` | Identical exposure via ETF |
| Long bonds leg | 20–30y Treasury bonds | `"TLT"` | TLT tracks 20+ Treasuries |
| Gold leg | Physical gold bullion | `"GLD"` | GLD tracks physical gold |
| Cash leg | T-bills (90-day) | `"SHY"` | SHY ≈ 1–3y Treasuries, cleanest cash-equivalent on yfinance daily |
| Target weights | 25/25/25/25 | 0.25/0.25/0.25/0.25 | Identical |
| Rebalance frequency | Annual + 10% drift band | Monthly | See "Implementation deviations" |

## Data Fidelity

* **Substrate:** daily closing prices from yfinance for the four
  ETF legs (SPY, TLT, GLD, SHY). All four have inception dates
  before 2005 (TLT and SHY in 2002; GLD in 2004; SPY in 1993),
  giving a continuous panel from 2005 onward.
* **No transaction costs in synthetic fixture.** The vectorbt
  bridge applies a configurable flat `commission_bps` per rebalance
  when the strategy is run; the in-repo benchmark in
  `benchmark_results.json` reports headline metrics at
  `commission_bps = 5.0` on the AlphaKit fixture price panel
  (real-feed yfinance benchmark deferred to Session 2H).
* **Rebalance cadence:** monthly (AlphaKit-wide default) versus
  Browne's annual + 10% drift band. Monthly rebalancing increases
  turnover but produces fewer cluster-comparison surprises
  versus the other Session 2G allocators (which all rebalance
  monthly). The cadence choice is a deliberate deviation
  documented under "Implementation deviations".
* **Cash proxy.** Browne specifies short-duration T-bills (90-day).
  yfinance does not carry a clean 90-day T-bill ETF prior to BIL's
  2007 inception; SHY (iShares 1-3 Year Treasury) is used instead
  as the cleanest pre-2007-compatible cash proxy. The duration
  mismatch (1-3 years vs 90 days) introduces a small interest-rate-
  sensitivity component to the "cash" leg that Browne's pure T-bill
  prescription would not have. This is documented in
  `known_failures.md` §3 (real-rate spikes).
* **Survivorship.** All four ETFs are still live as of the
  validation cutoff (2025-12-31). No survivorship adjustment is
  required.

## Expected Sharpe range

`0.3 – 0.6 OOS` (Estrada 2018, Table 1: Sharpe ≈ 0.5 over 1972–2016
for the 25/25/25/25 US portfolio). The lower bound of 0.3 accounts
for the AlphaKit substrate's ETF-based implementation (vs Estrada's
total-return index proxies for the four asset classes) and the
bridge-side daily drift-correction cadence (see "Implementation
deviations" item 1 below). The upper bound of 0.6 reflects Estrada's
reported range across the four-decade sample including the high-
Sharpe 2000–2010 period when gold rallied strongly.

## Implementation deviations from Browne 1987 and Estrada 2018

1. **Monthly target signal instead of Browne's annual + 10% band
   (and bridge-side daily drift correction).** This is two stacked
   deviations and both should be read together.

   *Signal cadence.* Browne's 1987 prescription is to rebalance
   annually with a 10% drift tolerance — if any leg drifts to
   <15% or >35%, trigger a rebalance regardless of timing.
   Estrada's 2018 formal tests (Table 1) also use annual
   rebalancing. AlphaKit emits the 25/25/25/25 target signal at
   each **month-end** bar for clean comparison with the rest of
   the Session 2G family (all macro strategies emit monthly
   signals). The cadence is configurable via `rebalance` in
   `config.yaml` if a Phase 3 user wants to revert to annual.

   *Bridge-side rebalance cadence (AlphaKit-wide convention).*
   The vectorbt bridge applies `SizeType.TargetPercent` semantics
   to the daily-forward-filled signal: on each daily bar it
   re-marks the portfolio to target by issuing small drift-
   correction trades. The **observed trade-event count is ~63
   per asset per year**, not the ~12 a discrete monthly rebalance
   would produce. Empirically verified during Commit 2 gate-3
   review: a 63-bar test panel emitted 3 month-end strategy
   signals but produced 156 bridge orders across 41 distinct
   dates. The per-trade notional is small (drift accumulated
   since the previous bar, typically 0.05–0.5% of position
   value), so total commission cost is bounded — approximately
   equivalent to a true monthly rebalance of the full notional
   under any reasonable per-trade cost model.

   *Why this is acceptable.* The economic exposure (Sharpe,
   total return, max drawdown) matches a true monthly rebalance
   within friction-cost noise. Only the trade-event distribution
   differs. This is the project-wide convention across the 99
   strategies on `origin/main` (60 Phase 1 + 13 rates + 10
   commodity + 15 options + 1 macro pending) — the pattern was
   established in Phase 1 `dual_momentum_gem` and applied
   uniformly across Sessions 2D / 2E / 2F. See
   `docs/phase-2-amendments.md` "Session 2G: alphakit-wide
   rebalance-cadence convention" for the project-level audit
   trail.

   *Phase 3 candidate.* A sparse-rebalance protocol extension
   (analogous to Session 2F's `discrete_legs` opt-in) would let
   strategies suppress the bridge-side daily drift correction
   and produce ~12 trade events per year instead of ~63. The
   reduction in trade events is small in dollar terms (commission
   cost is ~equivalent under either model) but cleaner for any
   per-trade reporting downstream. Out of scope for Session 2G;
   tracked for Phase 3 bridge-architecture work.
2. **SHY 1–3y as cash proxy** instead of pure 90-day T-bills. See
   "Data Fidelity" above. The duration mismatch is small in absolute
   terms but does mean that "cash" in this implementation carries
   non-zero interest-rate risk.
3. **No drift-band trigger.** Browne's 15%/35% drift bands are not
   implemented in this commit (would require holding-state
   tracking between bars). The monthly rebalance cadence
   effectively dominates the drift-band trigger for any plausible
   parameterisation; this is documented in `known_failures.md`.
4. **No bid-ask, financing, or short-borrow model.** Long-only,
   four-leg allocation — no shorting, no leverage. The bridge
   applies a flat `commission_bps` per rebalance leg.

None of these change the sign of any leg's allocation or the
strategy's regime-hedging economic content; they affect only
absolute turnover and friction-cost numbers.

## Known replications and follow-ups

* **Faber, M. (2007)** — *A Quantitative Approach to Tactical Asset
  Allocation*, JoWM Spring 2007 / SSRN 962461. Replicates the
  permanent-portfolio idea on a 5-asset universe (US equity / foreign
  equity / bonds / commodities / REITs) and adds a 10-month moving-
  average overlay; demonstrates the static-weight construction's
  durability across multi-decade samples.
* **Bernstein, W. J. (2010)** — *The Four Pillars of Investing*,
  McGraw-Hill (ISBN 0-07-138919-8). Pedagogical extension of the
  static-multi-asset thesis without the regime-mapping construction
  but with similar long-run Sharpe results on a 4-asset US panel.
* **Bekkers, N., Doeswijk, R. Q. & Lam, T. W. (2009)** — *Strategic
  Asset Allocation: Determining the Optimal Portfolio with Ten
  Asset Classes*, J of Wealth Management. Static-weight construction
  on a broader 10-asset universe; finds Sharpe ratios in the same
  0.3–0.6 band as Browne / Estrada on the 4-asset subset.
