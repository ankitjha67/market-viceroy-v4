# Paper — Metals-Only Time-Series Momentum (Asness §V, 2013)

## Citations

**Initial inspiration:** Moskowitz, T. J., Ooi, Y. H. & Pedersen, L. H.
(2012). **Time series momentum.** *Journal of Financial Economics*,
104(2), 228–250. [https://doi.org/10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003)

**Primary methodology:** Asness, C. S., Moskowitz, T. J. & Pedersen,
L. H. (2013). **Value and momentum everywhere.** *Journal of Finance*,
68(3), 929–985. Section V applies the 12/1 time-series-momentum rule
to commodity futures across an extensive cross-section. The metals
subset (gold, silver, copper, platinum) is part of the §V panel and
its per-asset contributions are reported in Table III.
[https://doi.org/10.1111/jofi.12021](https://doi.org/10.1111/jofi.12021)

BibTeX entries `moskowitz2012tsmom` (foundational) and
`asness2013value` (primary) are already registered in
`docs/papers/phase-2.bib` (originally introduced by `bond_tsmom_12_1`
in Session 2D and reused by `commodity_tsmom` earlier in Session
2E). No new bib entries are added.

## Why a metals-only sibling

Metals form an economically coherent sub-cluster within the broader
commodity universe. Two distinct stories sit inside the same
sub-panel:

* **Monetary metals (gold, silver)** — store-of-value, real-rate
  sensitivity, central-bank reserve flows.
* **Industrial metals (copper, platinum)** — global manufacturing
  cycle, EV/electrification demand, supply-side disruptions.

A metals-focused TSMOM book is a common practitioner allocation
(see e.g. AQR's commodity-strategy memos and Hurst/Ooi/Pedersen 2017
§IV) because the metals cross-section trades less synchronously with
energy and grains than the broader commodity panel, particularly
through inflation regimes where metals lead and softs/grains lag.

We ship the metals-only book as a separate strategy to expose this
sub-cluster as a first-class option for users who want metals beta
without energy or grain exposure. The cluster overlap with
`commodity_tsmom` is documented explicitly in `known_failures.md`
and accepted under the Phase 2 master plan §10 cluster-risk bar
(ρ > 0.95 triggers dedup; the predicted overlap is 0.75-0.90).

## Differentiation from sibling momentum strategies

* **`commodity_tsmom`** — same mechanic on a broader 8-commodity
  panel (energy + metals + grains). Strong cluster overlap with this
  strategy when metals dominate the broader cross-section; expected
  ρ ≈ 0.75-0.90.
* **Phase 1 `tsmom_12_1`** (trend family) — same mechanic on a
  6-asset balanced multi-asset universe (SPY/EFA/EEM/AGG/GLD/DBC).
  Overlap via GLD only; expected ρ ≈ 0.3-0.5 in metals-driven
  regimes, lower otherwise.
* **`commodity_curve_carry`** — different signal (carry / roll
  yield) on the same broader panel; expected ρ ≈ 0.2-0.4 (metals
  carry trades a different curve regime than grain carry).
* **`bond_tsmom_12_1`** (Session 2D rates family) — single-asset
  10Y treasury TSMOM. Different asset class, different universe;
  expected ρ ≈ 0.1-0.3.

## Published rules (Asness §V applied to a metals subset)

For each metal *m* and each month-end *t*:

1. Compute the trailing return over the 12 months ending one month
   prior — months ``[t-12, t-1)``. Skip the most recent month per
   the 12/1 convention (sidesteps short-term reversal).
2. **Sign-of-return** trade: long if positive, short if negative.
3. **Per-asset volatility scaling** to a constant target (10%
   annualised by default). Position size for metal *m* at month
   *t*::

       weight_m(t) = sign(lookback_return_m) × (vol_target / realised_vol_m)

4. Hold one month, rebalance monthly.

| Parameter | Asness §V value | AlphaKit default | Notes |
|---|---|---|---|
| Lookback | 12 months | 12 months | identical |
| Skip | 1 month | 1 month | identical |
| Vol target (per asset) | 40% annualised | 10% annualised | rescaled to portfolio level (see `commodity_tsmom`) |
| Vol estimator | EWMA, 60-day half-life | 63-day rolling σ | converges to same long-run estimate |
| Rebalance | monthly | monthly | identical |
| Holding period | 1 month | 1 month | identical |

### Why the rescaled vol target

Same rationale as `commodity_tsmom`: Asness §V's 40% per-asset
target assumes a much wider panel and a 2-3× gross-leverage budget;
restricted to a 4-metal universe, that target produces a portfolio
vol well above any practitioner risk budget. Rescaling to 10%
per-asset brings the 4-metal portfolio volatility into the 6-10%
range. *Sign* and *relative* sizing are unchanged — all
scale-invariant metrics (Sharpe, Sortino, Calmar) remain directly
comparable to the paper.

## Asness §V evidence on the metals sub-panel

Asness Table III decomposes the §V commodity TSMOM book by sector.
The metals contribution is reported with positive but lower Sharpe
than the energy and grains legs over the full 1985-2010 sample —
metals trend persistence is weaker than energy and stronger than
softs, and the cross-section is narrower (4 metals vs ~8 energy /
~6 grains in the §V panel).

For the AlphaKit 4-metal default we expect:

* **In-sample Sharpe (1985-2010)**: 0.3-0.5 on the metals sub-book
  (paper-matched window, smaller universe penalty).
* **OOS Sharpe (2018-2025)**: 0.2-0.5 — recent metals regimes
  (2020 silver squeeze, 2021-2022 copper supply shocks, 2024
  gold rally) have been trendy but with sharp reversals; the 12/1
  signal lags both directions.

## Implementation deviations from Asness §V

1. **Rolling σ instead of EWMA** — same rationale as
   `commodity_tsmom`: deterministic in CI, no exponential-decay
   state to seed; both estimators converge to the same long-run
   realised volatility.
2. **Per-asset leverage cap of 3×** so a collapse in realised vol
   cannot push weights to infinity. Asness §V does not need this
   because EWMA estimators are smoother.
3. **Portfolio-level vol target of 10%** instead of the paper's
   per-asset 40%. See "Why the rescaled vol target" above.
4. **No bid-ask, financing, or short-borrow model.** The bridge
   applies a flat ``commission_bps`` per leg.

None of these change the **sign** of the signal or the **relative
ordering** of weights, so the strategy remains faithful to the
paper's economic content.

## Known replications and follow-ups

* **Hurst, Ooi & Pedersen (2017)** — "A Century of Evidence on
  Trend-Following Investing", AQR. §IV documents metals as a
  persistent TSMOM sub-cluster on long-horizon data.
* **Erb & Harvey (2006)** — "The Strategic and Tactical Value of
  Commodity Futures", FAJ. Documents momentum and roll-yield
  separately on a metals sub-panel.
* **Baltas & Kosowski (2013)** — "Momentum Strategies in Futures
  Markets and Trend-Following Funds", EFA. Per-sector decomposition
  of the §V replication confirms the metals sub-cluster
  contribution.
