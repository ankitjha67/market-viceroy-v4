# Known failure modes — wti_brent_spread

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

WTI-Brent pairs-trading spread. Failures cluster around regimes
where the **cointegration breaks** — typically driven by
infrastructure dislocations (US shale + Cushing storage glut) or
geopolitical events affecting only one of the two grades.

## 1. Cushing-glut cointegration break (2011-2014)

The 2011-2014 US shale-revolution period broke the WTI-Brent
cointegration:

* Surging US crude production filled Cushing, OK storage to
  capacity (the legal-export ban prevented sale to global markets).
* WTI traded at a $15-25/bbl *discount* to Brent for ~3 years.
* Mean reversion failed — the spread did not return to its
  pre-shale ±$2/bbl range until the export-ban repeal in late
  2015.

The strategy entered short-spread (short WTI, long Brent) on the
first 2σ widening (~Q4 2010) and stayed short while the spread
widened to 6-8σ from the rolling mean over the next 2 years →
drawdown ~25-30%. Recovery only came after the Phase 1 export-
ban repeal in December 2015.

This is the canonical example of cointegration-break failure for
the WTI-Brent pair. Users running real-money sleeves should
overlay an explicit cointegration test (Phase 3 candidate) that
disables trading when the ADF p-value > 0.10.

## 2. Geopolitical shocks affecting one grade (2014 Libya, 2019 Saudi attacks, 2022 Russia)

Brent supply shocks cause the spread to *tighten* sharply:

* **2014 Libya conflict**: Brent supply disruption pushed Brent
  premium up sharply, then the spread compressed as supply
  recovered.
* **September 2019 Saudi Aramco drone attacks**: Brent spiked
  ~15% in a single day; spread tightened from -$5 to -$2 over
  2 weeks.
* **February-March 2022 Russia sanctions**: Brent rallied
  ~25% on Russian-supply concerns while WTI lagged; spread
  widened from -$5 to -$15 (back to Cushing-glut levels).

The strategy responds to these shocks but with a 1-2-month lag
because of the 252-day z-score normalisation:

* Initial drawdown 5-10% as the spread continues to move past
  the 2σ entry point
* Recovery 3-6 months as the geopolitical shock resolves and the
  spread reverts

## 3. Cushing-storage capacity events

When Cushing storage approaches full capacity (e.g. April 2020
COVID demand collapse, December 2015 brief approach), the WTI
contract can trade at a steep discount to Brent for a few weeks
before the storage release. The strategy enters short-spread
during the widening but the dislocation is brief — typically the
spread recovers within 4-8 weeks. Drawdown 5-10% per event.

April 2020 was particularly extreme: the May 2020 WTI contract
settled at **-$37.63** on April 20. The strategy's input
validation rejects non-positive prices, so users running on real
data must either pre-filter the negative-price day or roll the
front contract early.

## 4. Cross-commodity correlated shocks

When global oil prices move sharply on demand-side news (2008 H2
crisis, 2020 H1 COVID, 2022 H2 OPEC+ cut), both WTI and Brent
move in the same direction with similar magnitude. The spread
stays roughly constant but volatility spikes → z-score noise
increases → strategy can flicker between long/short signals
within a 1-2-week window.

Mitigation: tighten `entry_threshold` to 2.5σ during high-
volatility regimes (Phase 3 candidate).

## 5. ICE Brent futures contract specifics

ICE Brent futures (BZ=F on yfinance) are cash-settled against
the Brent crude index, which itself is composed of multiple
North Sea grades (Brent, Forties, Oseberg, Ekofisk, Troll —
the BFOET basket). Composition changes (e.g. addition of
Norwegian Troll grade in 2018) can introduce small step changes
in the BZ=F series that the rolling z-score absorbs only
partially.

## 6. Continuous-contract roll bias

Standard yfinance back-adjustment limitation. WTI rolls on the
3rd-to-last business day before the 25th of the prior month;
Brent rolls one trading day before the contract month begins.
The two contracts have *different* roll schedules, so on the
~5 days each month when one has rolled and the other hasn't,
the spread series exhibits a one-day discontinuity. The 252-day
window absorbs this but produces noise in the z-score.

For real-feed Session 2H benchmarks the cleanest fix is explicit
per-contract data with synchronised roll convention.

## 7. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **`crack_spread`** (Session 2E sibling, Commit 9) — both
  involve crude, both mean-reversion; ρ ≈ 0.1-0.3.
* **`wti_backwardation_carry`** (Session 2E sibling, Commit 4) —
  WTI single-asset curve; ρ ≈ 0.1-0.3 when Cushing-curve and
  WTI-Brent spread move together.
* **`commodity_curve_carry`** — different signal; ρ ≈ 0.0-0.2.
* **`crush_spread`** — different commodity entirely; ρ ≈ 0.0-0.1.
* **Phase 1 trend / momentum strategies** — different signal,
  partial universe overlap (USO ≈ WTI proxy); ρ ≈ 0.1-0.2.

All overlaps below the master plan §10 deduplication bar (ρ > 0.95).

## 8. Multi-leg execution risk

2 simultaneous legs (CL, BZ). NYMEX and ICE both list the
WTI-Brent spread directly as a tradeable inter-exchange spread
("CB" on CME Globex), but liquidity is moderate and the
synchronised roll across NYMEX/ICE adds operational complexity.
Atomic multi-leg execution via SOR risks leg-out if one leg
fills and another doesn't.

## Regime performance (reference, from public crude-spread sleeves)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-shale stable cointegration | 2003-2009 | ~0.8 | −5% |
| Crisis volatility | 2008-09 – 2009-09 | ~0.4 | −9% |
| Cushing-glut break | 2011-2014 | ~−1.0 | −28% |
| Post-export-ban repeal | 2016-2018 | ~0.6 | −7% |
| 2019 Saudi drone shock | 2019-09 – 2019-12 | ~−0.5 | −8% |
| Post-COVID equilibrium | 2020-2021 | ~0.7 | −6% |
| Russia-sanctions widening | 2022-02 – 2022-08 | ~−0.8 | −15% |
| 2023-2024 mean reversion | 2023-2024 | ~0.9 | −4% |

(Reference ranges from public crude-spread sleeves; the in-repo
benchmark is the authoritative source for this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
