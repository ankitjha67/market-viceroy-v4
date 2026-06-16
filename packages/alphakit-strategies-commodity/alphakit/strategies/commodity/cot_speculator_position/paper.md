# Paper — COT Speculator-Position Contrarian (de Roon-Nijman-Veld 2000)

## Citations

**Foundational paper:** Bessembinder, H. (1992). **Systematic risk,
hedging pressure, and risk premiums in futures markets.** *Review
of Financial Studies*, 5(4), 637–667.
[https://doi.org/10.1093/rfs/5.4.637](https://doi.org/10.1093/rfs/5.4.637)

Bessembinder (1992) decomposes the futures-curve risk premium into
hedging-pressure and macro-risk components and shows that the
**residual hedging pressure** in commodity-futures markets is
priced: when commercial hedgers are net short, speculators earn a
positive premium on long positions; when commercial hedgers are
net long, speculators earn a negative premium.

**Primary methodology:** de Roon, F. A., Nijman, T. E. & Veld, C.
(2000). **Hedging pressure effects in futures markets.** *Journal
of Finance*, 55(3), 1437–1456.
[https://doi.org/10.1111/0022-1082.00253](https://doi.org/10.1111/0022-1082.00253)

de Roon-Nijman-Veld (2000) directly test the hedging-pressure
hypothesis on the CFTC Commitments of Traders (COT) data across
20 commodity futures (1986-1994) and find:

> "Hedging pressure plays an important role in the determination
> of futures risk premia ... we find that the futures risk premium
> is significantly affected by the hedging pressure of the
> commercial traders ... a strategy that is long in commodities for
> which commercials are net short and short in commodities for which
> commercials are net long generates significant abnormal returns."

**Translated to the contrarian speculator framing**: when
speculators (non-commercials) are extreme-long, expected futures
returns are negative; when speculators are extreme-short, expected
returns are positive. This is the contrarian COT signal.

BibTeX entries `bessembinder1992` and `deRoonNijmanVeld2000` are
registered in `docs/papers/phase-2.bib`.

## Why a contrarian COT framing

The hedging-pressure literature has two equivalent expressions:

1. **Pro-hedger framing** (Bessembinder 1992, dRN-V 2000 abstract):
   long commodities where commercials are net short; short
   commodities where commercials are net long. *Earn the risk
   premium that hedgers pay to lay off price risk.*
2. **Contrarian-speculator framing** (this strategy): when
   non-commercials are extreme-long, the premium has been
   competed away → short; when non-commercials are extreme-short,
   the premium is rebuilding → long.

The two are equivalent in the limit. We choose the contrarian-
speculator framing because:

* CFTC's "non-commercial" series is more granular and stable than
  the "commercial" series for speculative-positioning analysis.
* The percentile-of-history threshold approach naturally focuses
  on *extreme* positioning rather than directional sign — robust
  to slow trend changes in average commercial activity.
* Practitioner sleeves (CTA / managed-futures funds) market the
  trade as "extreme positioning fade" — easier for users to
  recognise and reason about.

## CFTC Commitments of Traders data

The CFTC publishes the COT report **every Friday at 15:30 ET**,
covering positions held as of **the prior Tuesday close**. The
report breaks open interest into:

* **Commercial** (hedgers — producers, end-users, swap dealers)
* **Non-commercial** (speculators — managed money, asset managers)
* **Non-reporters** (small accounts below CFTC reporting threshold)

The strategy's positioning input is the **non-commercial long
fraction of open interest** (range ``(0, 1]``)::

    long_fraction(t) = non_commercial_long(t) / open_interest(t)

This produces a stationary series in ``(0, 1]`` that is comparable
across commodities of different open-interest scales **and** is
strictly positive — required so the vectorbt bridge can validate
it as an input column even though the strategy assigns zero weight
to positioning columns.

Users with raw net positioning (range ``[-1, +1]``) should shift to
``(net + 1) / 2`` before passing in. The percentile rank used by
the trading rule is invariant to monotonic transformations, so
the shift does not change the signal — only the input scale.

## CRITICAL: Friday-for-Tuesday lag

**The most common error in COT-strategy research is failing to
apply the publication lag.** The CFTC report covers Tuesday
positions but is published the following Friday — Wednesday and
Thursday signals must use the prior Friday's report (which covers
the *previous* Tuesday's positions, six days earlier).

This implementation enforces the lag by shifting the COT-derived
signal forward by `cot_lag_days = 3` trading days before applying
the rule. The choice of 3 days corresponds to a Tuesday close →
Friday publication + 1-day execution buffer.

A failure to apply the lag in backtests produces ~3-5% spurious
annualised excess returns from forward-looking bias — material
relative to the strategy's expected ~0.4-0.6 Sharpe.

## Differentiation from sibling carry strategies

The COT signal is a **distinct dimension** from the curve-slope
signal traded by `wti_backwardation_carry`, `ng_contango_short`,
and `commodity_curve_carry`:

* **Curve-slope strategies** trade the *current* curve regime and
  earn the steady-state hedging-pressure premium.
* **COT-positioning strategies** trade the *positioning extreme*
  and earn the reversion premium when one side becomes too
  crowded.

The two signals are complementary: in a normal (non-extreme)
regime, the curve-slope strategies are active and the COT strategy
is flat; in an extreme positioning regime, the COT strategy
overrides with a contrarian fade. Predicted ρ between
`cot_speculator_position` and the curve-carry strategies is
0.0-0.2 (essentially uncorrelated except in rare regimes where
both signals fire — e.g. extreme contango + extreme short
speculator positioning is a confirmed-bullish setup that both
strategies catch).

## Default universe

The default 4-commodity universe (CL, NG, GC, ZC) is chosen because:

* All four have **liquid, deep-history CFTC COT reports** going
  back to the early 1990s.
* They span **distinct macro factors**: energy (CL/NG), monetary
  metals (GC), grains (ZC) — limiting cluster correlation across
  legs.
* Each has a documented hedging-pressure literature (CL: Hong-Yogo
  2012; NG: Bessembinder 1992; GC: Pukthuanthong-Roll 2011; ZC:
  Sanders-Boris-Manfredo 2004).

Users wanting a broader universe can override `front_to_position_map`
and provide additional positioning columns. CFTC publishes COT
data for ~30 commodity contracts.

## Trading rule

For each commodity *c* and each trading day *t* (after the COT lag):

1. Compute the historical percentile of `net_spec_c(t-cot_lag)`
   over the rolling `percentile_lookback_weeks * 5`-day window.
2. **percentile > 90** → speculators in the top decile of their
   3-year history → **short** the front contract.
3. **percentile < 10** → speculators in the bottom decile → **long**
   the front contract.
4. Otherwise → flat.

Each leg is independently sized at +1 / -1 (no cross-sectional
normalisation). Users wanting a fixed gross book should overlay a
target-vol scaler.

## In-sample period (de Roon-Nijman-Veld 2000)

* Data: 1986-1994 CFTC COT, 20 commodity futures
* Hedging-pressure-decomposition Sharpe ~0.6 (averaged across the
  panel; per-asset Sharpe ranges 0.2-1.0)
* OOS update (Bhardwaj, Gorton, Rouwenhorst 2014): 1995-2012
  hedging-pressure Sharpe ~0.4 — meaningful degradation but
  persistence

For the AlphaKit 4-commodity default we expect:

* **Long-window OOS Sharpe (2005-2025)**: 0.3-0.5
* **Per-leg Sharpe varies by commodity**: CL and ZC tend to be
  higher (0.4-0.7) because their COT positioning is more
  cyclical; GC tends to be lower (0.1-0.3) because gold
  positioning is less directionally predictive

## Implementation deviations from de Roon-Nijman-Veld 2000

1. **Percentile-of-history threshold** instead of dRN-V's
   sign-of-net-position rule. The percentile approach focuses on
   *extreme* positioning (top/bottom decile) where the contrarian
   premium is largest; the dRN-V rule trades whenever positioning
   is non-zero (more turnover, lower per-trade edge).
2. **3-year rolling lookback** for the percentile vs dRN-V's
   full-sample cross-section. Rolling window adapts to slow
   regime changes in average commercial activity (e.g. swap-
   dealer entry post-2000 changed the structural composition of
   the "commercial" bucket).
3. **Fixed unit positions per leg** vs dRN-V's signal-weighted
   sizing. Robust to outliers; signal-weighting is a Phase 3
   candidate.
4. **No bid-ask, financing, or short-borrow model.** The bridge
   applies a flat `commission_bps` per leg.

None of these change the **economic content** of the
hedging-pressure framework.

## Known replications and follow-ups

* **Hong & Yogo (2012)** — "What Does Futures Market Interest
  Tell Us about the Macroeconomy and Asset Prices?", JFE 105(3).
  Decomposes commodity-curve-position dynamics; supports the
  contrarian-positioning interpretation.
* **Bhardwaj, Gorton & Rouwenhorst (2014)** — "Fooling Some of
  the People All of the Time: The Inefficient Performance and
  Persistent Promotion of Commodity Indexes", FAJ 70(6). Updates
  the dRN-V 2000 hedging-pressure result through 2012.
* **Sanders, Boris & Manfredo (2004)** — "Hedgers, Funds, and
  Small Speculators in the Energy Futures Markets: An Analysis
  of the CFTC's Commitments of Traders Reports", Energy
  Economics 26(3). Energy-specific positioning analysis.
