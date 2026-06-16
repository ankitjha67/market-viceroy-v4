# Known failure modes — bond_carry_rolldown

> Carry strategies look like free money in steep-curve regimes and
> like a duration-overlay disaster when the curve flattens or
> inverts unexpectedly. This is the cost of the term premium —
> compensation for accepting that risk.

Single-asset duration overlay: long the target long bond when the
curve is steep enough (z-score of slope proxy < −1.0σ), flat
otherwise. The strategy will lose money in the regimes below.

## 1. Curve flattens / inverts after entry (2018, 2022)

The strategy enters when the curve is steep and stays in until the
slope proxy reverts. If yields rise across the curve and the
long-end leads (curve flattens or inverts), the long target bond
loses to duration alone — and the strategy has no parallel-shift
hedge by design.

Expected behaviour during a 2022-style rate shock:

* Strategy is long TLT going into 2022 (curve was steep at end-2021)
* TLT loses 30% over Jan-Oct 2022 as 10Y yield rises 250 bps
* Strategy doesn't exit until the slope proxy z-score reverts past
  −0.25σ, which doesn't happen until the curve actually inverts
  in mid-2022

Drawdowns of 25-35% during sustained bear bond markets are
expected. This is the cost of the duration premium.

## 2. False signals during transition regimes (e.g. early 2020)

When the curve transitions abruptly from inverted (early 2020) to
steep (mid-2020 post-Fed-cuts), the slope proxy goes from low
log_spread to high log_spread quickly. The z-score lags by the
``zscore_window`` length, so the strategy can:

* Stay LONG into the first leg of the inversion (carry signal still
  active from earlier steep regime)
* Then go FLAT just as the new steep regime begins (entry threshold
  not crossed yet by the post-shock z-score)

Mitigation: shorten ``zscore_window`` to 126 (6 months) for faster
reaction in regime transitions, accepting more whipsaw in stable
regimes.

## 3. Proxy mismatch with true yield-curve carry

The implementation uses a price-space slope proxy
``log_spread = log(P_long) - log(P_short)``. This is monotone in the
yield spread but is **not** the carry itself. True carry includes:

* Current 10Y yield (level term)
* Rolldown contribution from the curve's slope at the 10Y point
  specifically (not the 2-10 average slope)

When the curve is non-monotonic (e.g. inverted at the front-end and
steep at the back-end), the 2-10 slope can mis-represent the actual
10Y rolldown. This is rare but documented in the early-1980s and
2022 rate-shock periods. Real-feed Session 2H benchmarks should
substitute an explicit yield-curve-derived carry signal for the
proxy.

## 4. Cluster correlation with sibling strategies

Expected ρ with siblings:

* `bond_tsmom_12_1` — momentum on bond price; activates in similar
  steep-curve regimes (when long-end has been outperforming).
  Expected ρ ≈ 0.5–0.7 in steep-curve regimes, lower otherwise.
* `curve_flattener_2s10s` — both enter in steep-curve regimes but
  for opposite reasons (flattener bets on mean-reversion, carry-
  rolldown bets on persistence). Expected ρ ≈ −0.3 to +0.3
  depending on which view realises.
* `curve_steepener_2s10s` — opposite of the flattener; enters in
  flat-curve regimes when carry-rolldown is *flat*. Expected ρ
  near zero — the strategies trade in non-overlapping regimes.
* `bond_carry_roll` (in `alphakit-strategies-carry`) — cross-
  sectional version of the same KMPV framework. Single-asset US-only
  vs cross-country G10 trades different information; expected ρ ≈
  0.3–0.5 in the US 10Y component.
* `g10_bond_carry` (Session 2D Commit 11) — cross-country bond
  carry; expected ρ ≈ 0.3–0.5 in regimes where US slope dominates
  the cross-country signal.

None of these cross 0.95. Phase 2 master plan §10 cluster-risk
acceptance: shippable.

## 5. Single-asset concentration risk

The strategy holds *only* the target long bond when active. Any
idiosyncratic shock to the long-end alone (e.g. Treasury auction
failure, downgrade, 30Y-specific liquidity event) hits the position
unhedged. The 2-month-or-longer typical holding period magnifies
the exposure to any tail event during the window.

## 6. Negative-yield breakdown

Below 0% yield (Europe 2014–2022, hypothetical US negative-rate
scenario) the carry signal interpretation breaks down:

* Negative yields invert the sign of the coupon-income contribution
* Rolldown remains positive (a steep negative-yield curve still
  has the long-end pricing into the short-end as the bond ages)
* The price-space proxy continues to function, but the
  *interpretation* of "high carry" no longer maps cleanly to "high
  expected return"

The strategy is calibrated for the 0–8% USD yield regime. Outside
that range, re-validation against a regime-specific term-premium
model is required.

## Regime performance (reference, gross of fees, single-asset US 10Y carry-rolldown)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Steep curve (2002–2007) | 2002-01 – 2007-06 | ~0.9 | −5% |
| Pre-recession flattening (2018) | 2018-01 – 2018-12 | ~−0.4 | −7% |
| Pandemic re-steepening (2020 H2) | 2020-07 – 2020-12 | ~1.5 | −2% |
| Rate shock (2022) | 2022-01 – 2022-12 | ~−1.8 | −32% |
| Inversion plateau (2023) | 2023-01 – 2023-12 | ~0.0 (mostly flat) | −5% |

(Reference ranges from the KMPV (2018) US 10Y carry sleeve and from
SocGen / AQR carry-strategy reports; the in-repo benchmark is
authoritative for this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
