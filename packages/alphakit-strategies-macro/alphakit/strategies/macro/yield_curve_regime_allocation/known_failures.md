# Known failure modes — yield_curve_regime_allocation

> "Lost 18% in 2018, recovered in 2022" beats silence. Every
> AlphaKit strategy must document the regimes where it
> under-performs so users can size it intelligently and avoid
> surprise drawdowns.

EH (1991) / APW (2006) yield-curve-slope 3-cell regime allocation
across SPY / TLT / GLD driven by two raw yield-level informational
columns (DGS10, DGS2 → 2s10s slope computed internally). Third
consumer of the regime-state primitive.

## 1. False-positive inversions

An inverted yield curve forecasts recession — but not every
inversion is followed by an immediate recession. False positives:

* **1998 (LTCM / Asian crisis):** the curve briefly inverted; no
  recession followed until 2001. A strategy reacting to the 1998
  inversion would have rotated defensive and missed the 1999
  dotcom equity rally.
* **2019 (mid-cycle inversion):** the 2s10s inverted in August
  2019; the recession (COVID 2020) was ~6 months later but driven
  by an exogenous shock, not the slowdown the inversion forecast.

Expected behaviour during false-positive inversions:

* Defensive allocation (0% equity) for the duration of the
  inversion + the lead time.
* Opportunity cost of 5-15% per year vs a balanced benchmark over
  the false-positive window.

This is the canonical cost of the yield-curve signal: it has a
long and variable lead time and a non-trivial false-positive rate.

## 2. Early-warning lead time (the curve inverts ~12-18 months early)

The yield curve typically inverts 12-18 months *before* the
recession it forecasts. A strategy that rotates defensive on the
inversion will be early — sometimes by more than a year — and will
miss the late-cycle equity melt-up that frequently follows the
initial inversion.

Historical example: the 2006 inversion preceded the 2008 recession
by ~18 months. The strategy would have rotated defensive in 2006
and missed the 2006-2007 equity rally (SPY +20%+ before the 2008
peak).

Expected behaviour: the strategy is *early* to defensive. In long-
lead-time inversions the cumulative opportunity cost can exceed the
recession-avoidance benefit.

## 3. DGS2-vs-DGS3MO bridge-positivity constraint (LOAD-BEARING)

Estrella-Hardouvelis (1991) and the Cleveland Fed model use the
10y-3m spread. The natural short leg is `DGS3MO`. However, `DGS3MO`
prints exactly `0.0` on several ZIRP days (2011, 2020-2021).

The vectorbt bridge treats every input column — including the
zero-weight informational yield columns — as a `close` price and
asserts `order.price > 0`. A `0.0` DGS3MO print would trip this
assertion even though the column is informational.

The strategy therefore uses **`DGS2`** (2-year) as the short leg:
the 2-year yield always carries a term premium and stays strictly
positive at the ZIRP lower bound. The 2s10s slope is ~0.9-
correlated with the 10y-3m measure.

This is documented in `docs/phase-2-amendments.md` "Session 2G:
informational columns must be positive-valued (vectorbt bridge
constraint)" and is the load-bearing reason for the DGS2 choice.
It also illustrates the general regime-state-group rule: pass raw
positive level series and compute any (possibly-negative) derived
signal internally.

## 4. Regime-boundary whipsaw

The 3-cell classification uses hard thresholds (steep ≥ 1.0%,
inverted < 0.0%). When the slope oscillates near a threshold (e.g.
hovering around 0% during a slow flattening), the regime flips
between flat and inverted, producing whipsaw turnover with large
3-leg reallocations (flat is 40/40/20; inverted is 0/60/40).

Expected behaviour near regime boundaries:

* 100-200% notional turnover per regime flip.
* Whipsaw cost of 2-5% per year when the slope hovers near a
  threshold (e.g. 2019 when the 2s10s oscillated around 0%).

Mitigation: widen the threshold deadbands or add a confirmation
lag. The constructor exposes `steep_threshold` and `flat_threshold`.

## 5. Publication-lag handling (inherited from Commit 8)

Inherits the publication-lag discipline. Both yield columns are
lagged by `yield_lag_months` (default 1) before the slope is
computed. Treasury yields are published daily with negligible lag,
so the 1-month lag is conservative (applied for parity with the
other Session 2G regime-state strategies). Setting
`yield_lag_months=0` is defensible for yields specifically (unlike
CPI/GDP/recession-probability which have genuine multi-week
publication lags).

## 6. Rebalance-cadence: monthly signal, daily bridge-side drift correction

Inherits the AlphaKit-wide convention. For
yield_curve_regime_allocation specifically:

* ~63 daily drift-correction events per asset per year on the
  three tradable legs.
* Plus regime-flip events (0-4 per year) with 3-leg reallocations.
* Zero events on both yield informational columns (DGS10, DGS2
  always weight 0.0).

See `docs/phase-2-amendments.md` "Session 2G: alphakit-wide
rebalance-cadence convention".

## 7. Cluster correlation with sibling strategies

Predicted correlations on synthetic-fixture data; verified in
Session 2H against real-feed data:

* **Phase 2 Session 2G `recession_probability_rotation`**
  (Commit 8) — closest cluster sibling. The Cleveland Fed
  recession-probability model uses the yield-curve slope (10y-3m)
  as its primary input, so this strategy's 2s10s slope and Commit
  8's recession-probability are driven by overlapping information
  (the two slope measures are ~0.9 correlated). Expected ρ ≈
  **0.50-0.70** — the highest pairwise correlation in the
  regime-state group. This is the deliberate family pair that
  Commit 8's paper.md and known_failures.md flagged. Both
  strategies ship because they are the continuous-slope (this) and
  probit-probability (Commit 8) implementations of the same
  underlying yield-curve signal — a legitimate methodology pair,
  well below the ρ > 0.95 dedup-review bar.
* **Phase 2 Session 2G `growth_inflation_regime_rotation`**
  (Commit 9) — CPI + GDP, 4-cell. Expected ρ ≈ 0.40-0.60.
* **Phase 2 Session 2G `fed_policy_tilt`** (Commit 11) — fed
  funds rate. The 2-year yield tracks fed-funds expectations, so
  there is signal overlap on the short end. Expected ρ ≈
  0.40-0.60.
* **Phase 2 Session 2G `inflation_regime_allocation`** (Commit 12)
  — CPI YoY. Expected ρ ≈ 0.30-0.50.
* **Phase 2 Session 2G `permanent_portfolio`** (Commit 2) —
  static allocation. Expected ρ ≈ 0.30-0.50.

All pairwise ρ values within the regime-state group sit in the
0.30-0.70 range — a substantial macro-state common factor but
well below the ρ > 0.95 deduplication-review bar.

## Regime performance (reference, from EH 1991 + APW 2006 + practitioner data)

| Regime | Example window | Sharpe | Max DD |
|---|---|---|---|
| Steep curve (post-recession recovery) | 2003-2005, 2010-2013 | ~0.8 (equity-heavy) | −6% |
| Flat curve | 2005-2006, 2017-2018 | ~0.4 | −10% |
| Inverted → recession captured | 2007-Q3 → 2009 | ~0.5 (defensive) | −12% |
| Inverted false-positive | 1998, mid-2019 | ~−0.2 (early defensive) | −5% |
| Long-lead inversion (early defensive) | 2006-2007 | ~0.2 (missed melt-up) | −8% |

(Reference ranges from EH 1991, APW 2006, and practitioner
sources; the in-repo benchmark is the authoritative source for
this implementation — see
[`benchmark_results.json`](benchmark_results.json).)
