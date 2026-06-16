# Known failure modes — gtaa_cross_asset_momentum

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

AMP §V 12/1 time-series momentum on a 9-ETF cross-asset panel. The
strategy will lose money in the regimes below; none of these are
bugs, they are the cost of the trend-following risk premium on a
multi-asset book.

## 1. Trendless / range-bound macro regimes (2015-16, 2017-18)

When equity, bonds, and commodities oscillate without establishing
durable trends, the 12/1 signal repeatedly enters long after a brief
rally only to be stopped out by a reversion (and the same for
shorts). CTA-style cross-asset trend sleeves (SG Trend, BTOP-50)
under-performed in 2015-2018 with several posting Sharpe in the
**0 to −0.5** range over multi-year windows.

Expected behaviour for `gtaa_cross_asset_momentum` in similar regimes:

* Sharpe of 0.0 to −0.5 over the regime window.
* Drawdown of 8–15% from peak.
* High monthly turnover (the cross-asset TSMOM book flips
  repeatedly across multiple legs).

## 2. Sharp regime changes (2008 GFC, 2020 March COVID, 2022 H1)

When asset prices reverse sharply on macro shocks, the 12/1 signal
lags by months. The strategy holds the wrong position into the
reversal and takes a 1–2 quarter drawdown before flipping. 2008
GFC: held long equity/credit/commodity legs into the September
2008 panic; took 3–6 month drawdown before flipping. 2020 March
COVID: similar pattern at compressed velocity — the entire 1–6
month signal lag played out in 3 weeks.

Expected behaviour during sharp cross-asset reversals:

* Drawdown of 12–20% before the signal flips direction.
* Recovery as the new trend establishes (typically 6–12 months
  post-reversal).

## 3. Cross-sectional dispersion collapse (2020 March)

When all asset classes move in the same direction (universal
risk-off in 2020 March; broad reflation in 2021 Q1), the cross-
asset diversification benefit collapses and the long-short book
becomes a directional bet on the dominant trend. If the directional
bet is wrong, multiple legs lose simultaneously.

Mitigation: pair the strategy with a market-regime filter (e.g.
exit when realised cross-asset vol exceeds 2σ above its long-run
mean). Phase 3 candidate.

## 4. Real-rate spikes (2022)

When real interest rates rise sharply, **multiple legs lose
simultaneously**: long bonds (TLT) drop, gold (GLD) stagnates,
real estate (VNQ) falls. The 2022 Fed-tightening cycle illustrated
this acutely — the strategy was long bonds and real estate going
into 2022 (positive 12-month returns through 2021), then took a
~25% drawdown across the bond / real-estate legs before the signal
flipped.

Expected behaviour in real-rate-spike regimes:

* Sharpe of −0.3 to −0.7 over the regime window.
* Drawdown of 15–25% (the strategy's worst-case regime).

Mitigation: pair with a real-yield-aware overlay (Phase 1
`real_yield_momentum` rates family, or Session 2G
`growth_inflation_regime_rotation`).

## 5. Rebalance-cadence: monthly signal, daily bridge-side drift correction

This strategy inherits the AlphaKit-wide convention: monthly
target signal emitted at month-end, daily bridge-side drift
correction by vectorbt's ``SizeType.TargetPercent`` semantics.
Empirical trade-event count: **~63 events per asset per year**
(not the ~12 a discrete monthly rebalance would produce).

Per-trade notional is small (drift since the previous bar,
~0.05–0.5% of position value); total commission cost is bounded
under any reasonable per-trade model.

For the full project-wide audit trail of the cadence convention,
see ``docs/phase-2-amendments.md`` "Session 2G: alphakit-wide
rebalance-cadence convention".

## 6. Real-estate substrate quirk

The VNQ (US REITs) leg has a structural feature that AMP §V's
futures universe does not: REIT prices are sensitive to *both*
interest rates *and* the underlying real-estate cash flows. This
means VNQ's 12-month momentum can flip *before* either the bond
leg (TLT) or the equity leg (SPY) flips — VNQ acts as an
"early warning" cross-asset signal in some regimes.

In rising-rate regimes (2022), VNQ flipped to negative momentum
in 2022 Q2 — earlier than TLT (Q3) or SPY (Q4). The strategy
captured this correctly by going short VNQ ahead of the broader
bond / equity flip. In falling-rate regimes (post-2008, late
2020), the reverse pattern: VNQ rallied first.

This is **not** a failure mode — it is a structural advantage of
the multi-asset universe (cross-asset signals reveal regime
transitions earlier than any single-asset signal). It is
documented here for transparency.

## 7. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **Phase 1 `tsmom_12_1`** (trend family) — same TSMOM mechanic
  on a narrower 6-ETF panel ``(SPY, EFA, EEM, AGG, GLD, DBC)``,
  cited on MOP 2012. The 6-ETF universe is a subset of this
  strategy's 9-ETF panel; the overlapping 6 legs trade identical
  signals. Expected ρ ≈ **0.65–0.85** when cross-asset momentum
  is the dominant signal; lower when the added TLT / HYG / VNQ
  legs diverge. **This is the most important cluster overlap**
  and is documented as a cluster-risk acceptance per the Phase 2
  master plan §10 bar (ρ > 0.95 triggers deduplication review;
  0.65–0.85 is below that bar but high enough to warrant explicit
  documentation).
* **Phase 1 `dual_momentum_gem`** (trend family) — 3-asset
  absolute + relative momentum on US equity / Intl equity /
  bonds; discrete 100%-allocation switching. Expected ρ ≈
  0.30–0.50 (correlated direction but discrete-vs-continuous
  weighting philosophy).
* **Phase 2 `commodity_tsmom`** (commodity family) — TSMOM on
  commodity futures only; this strategy's GLD + DBC legs overlap.
  Expected ρ ≈ 0.30–0.50.
* **Phase 2 `bond_tsmom_12_1`** (rates family) — single-asset 10Y
  treasury TSMOM; this strategy's TLT leg overlaps. Expected ρ ≈
  0.20–0.40.
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  static 25/25/25/25 on a broad-asset universe. Expected ρ ≈
  0.40–0.60 in trending regimes (when GTAA momentum aligns with
  permanent-portfolio constituents) and lower in mean-reverting
  regimes.

## 8. Vol-target instability when realised vol is near zero

When an asset's realised vol falls to near zero (e.g. AGG in
low-volatility Treasury regimes), ``vol_target / realised_vol →
∞``. The leverage cap (`max_leverage_per_asset = 3.0`) prevents
this from blowing up the backtest, but it does mean that a
low-vol asset contributes a large weight to the gross book until
vol reverts. Mitigation is the leverage cap; documented in the
strategy's edge-case docstring.

## Regime performance (reference, from CTA cross-asset sleeves + AMP §V Table III)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-GFC trending (2003-07) | 2003-01 – 2007-06 | ~1.0 | −4% |
| GFC trend capture (2007-09) | 2007-10 – 2009-03 | ~1.4 | −10% |
| Post-GFC reflation (2010-14) | 2010-01 – 2014-12 | ~0.5 | −12% |
| Range-bound (2015-18) | 2015-01 – 2018-12 | ~0.0 | −15% |
| Post-COVID reflation (2020-21) | 2020-04 – 2021-12 | ~1.0 | −6% |
| Real-rate spike (2022) | 2022-01 – 2022-12 | ~−0.5 | −22% |

(Reference ranges from CTA cross-asset trend sleeves, AMP §V Table
III, and HOP 2017 Table 2; the in-repo benchmark is the
authoritative source for this implementation — see
[`benchmark_results.json`](benchmark_results.json).)
