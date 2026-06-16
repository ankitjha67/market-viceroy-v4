# Known failure modes — curve_flattener_2s10s

> Mirror image of the steepener. Same family of risks, same regime
> dependencies, but flipped: the flattener bleeds during *prolonged
> steepening* (e.g. 2009–2010 post-recession curve normalisation)
> rather than during *prolonged inversion*.

DV01-neutral 2s10s flattener with z-score entry/exit hysteresis on
the log-price spread. The strategy will lose money in the regimes
below.

## 1. Prolonged curve steepening (2009–2010, 2020–2021)

After every recession the Fed cuts the policy rate aggressively, the
short-end yields collapse, and the curve steepens dramatically. The
2s10s spread can stretch to +250–300 bps and stay there for 12–18
months — well above any 1σ threshold. The flattener enters early
(when z first crosses −1σ) and bleeds DV01-neutral residual carry
plus borrow cost while the curve continues to steepen.

Expected behaviour during a 2009-style sustained steepening:

* Flattener active for the entire steepening window
* Drawdown of 8–18% from entry to peak steepness (residual carry +
  imperfect DV01 hedging)
* Eventual mean-reversion back to ~150 bps spread, but only after
  the Fed begins raising rates (12–24 months later)

Sizing implication: like the steepener, this is a multi-month
strategy minimum. Don't size it to a 1-month risk budget.

## 2. Carry receive during steep regimes

Whereas the steepener has *negative* carry (short-end yields less
than long-end), the flattener has *positive* carry: the long-leg
long-end yields more than the short-leg short-end. The position
earns ~80–150 bps annualised on carry alone, before transaction
and borrow costs, while waiting for the spread to narrow.

This is one regime where the flattener is *more* forgiving than the
steepener: even when the entry timing is poor, the carry partially
offsets the bleed. But it doesn't fully offset a sustained 100+ bps
move against the position.

## 3. Imperfect DV01 neutrality

Identical to the steepener. The default duration ratio (8.0 / 1.95
≈ 4.10) is the par-yield ratio of constant-maturity 10Y and 2Y
Treasuries, and drifts with the yield level:

* At 4% par yield: ratio ≈ 4.23 — close to default.
* At 1% par yield: ratio ≈ 4.62 — default under-shorts the long-end
  by ~12%, leaving residual exposure to parallel rate moves.
* At 8% par yield: ratio ≈ 3.79 — default over-shorts the long-end
  by ~8%.

In a 50 bps parallel rally (yields fall), the worst-case bias is
±20–25 bps of P&L per unit of signal. Documented as a known failure;
real-feed Session 2H benchmarks should re-estimate durations from
the ETF basket or the FRED yield level.

## 4. ETF basket vs constant-maturity drift (real-data only)

When run against TLT/SHY rather than constant-maturity Treasuries,
the underlying basket changes monthly. TLT's effective duration is
17, not 8. The strategy operates on log-price spreads, so the *sign*
of the signal is preserved, but the DV01-neutral weights are wrong
by a factor of ~2.

Real-feed Session 2H mitigation: rescale the durations to match the
ETF basket, or substitute IEF (7-10Y) for TLT to keep duration
closer to 8.

## 5. Cluster correlation with other rates strategies

Expected ρ with siblings:

* `curve_steepener_2s10s` — mirror-image **regime trigger**, NOT
  mirror-image signal. Both produce binary `signal ∈ {0, 1}` (not
  ±1): flattener fires only when `z < −entry_threshold`; steepener
  fires only when `z > +entry_threshold`. They trade **mutually
  exclusive z-score tail regimes** — z can't be both > +1 and < −1,
  so they never co-fire. When |z| < entry_threshold (the common
  regime, ~70% of bars), both signals are zero. Daily-return
  contributions therefore never co-occur, giving **expected ρ ≈ 0
  by construction** — NOT ρ ≈ −1.0 as earlier docs (pre-Session 2K-4)
  suggested. The S2K-4 29×29 keyed cluster empirically confirmed
  ρ = +0.000. Shipping both is still a documented user choice
  (covers both tail regimes); the pair does NOT trigger the Phase 2
  master plan §10 cluster-risk deduplication review under the
  corrected prediction.
* `curve_butterfly_2s5s10s` — different signal (PCA-driven on the
  2-5-10Y triplet) but overlapping when the 2s10s slope dominates
  the third PC; expected ρ with the flattener ≈ 0.4–0.6.
* `bond_carry_rolldown` — when the curve is steep, the carry-
  rolldown trade goes long the steep curve while the flattener goes
  long the long-end. Expected ρ ≈ 0.3–0.5 in normal regimes.

## 6. Single-pair concentration risk

A 2s10s-only flattener has no protection against curvature changes.
The 2s5s and 5s10s sub-spreads can move independently; the flattener
captures none of that P&L. Users seeking curve-shape exposure with
curvature hedging should look at `curve_butterfly_2s5s10s`.

## Regime performance (reference, gross of fees, DV01-neutral 2s10s flattener)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Late-cycle flattening into inversion (2018–2019) | 2018-01 – 2019-08 | ~1.2 | −4% |
| Post-recession steepening (2009–2010) | 2009-06 – 2010-12 | ~−1.2 | −13% |
| Pandemic steepening (2020–2021) | 2020-04 – 2021-04 | ~−0.8 | −10% |
| Inversion plateau (2022 H2 – 2023) | 2022-10 – 2023-12 | ~0.6 | −5% |

(Reference ranges from CTA-reported 2s10s slope sleeves and from
academic papers on slope-based prediction; the in-repo benchmark
is the authoritative source for this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
