# Paper — Credit-Spread Momentum (Jostova et al. 2013)

## Citation

**Primary methodology:** Jostova, G., Nikolova, S., Philipov, A. &
Stahel, C. W. (2013). **Momentum in corporate bond returns.**
*Review of Financial Studies*, 26(7), 1649–1693.
[https://doi.org/10.1093/rfs/hht022](https://doi.org/10.1093/rfs/hht022)

BibTeX entry: `jostova2013momentum` in `docs/papers/phase-2.bib`.

## Why a single citation

Jostova et al. (2013) §III specifies the trailing-6-month-return
ranking and documents the cross-sectional / time-series momentum
result on corporate bonds. The mechanic is fully specified by this
paper; no separate foundational paper is needed.

## Differentiation from sibling momentum strategies

* **`bond_tsmom_12_1`** — single-asset 12/1 momentum on Treasuries.
  Different asset class (sovereign vs corporate); expected ρ ≈
  0.3-0.5 in tandem-rates regimes, lower otherwise.
* **`real_yield_momentum`** — TIPS-derived momentum. Different
  asset class (real-rate-linked sovereign vs corporate); expected
  ρ ≈ 0.2-0.4.
* **`duration_targeted_momentum`** — cross-sectional duration-
  adjusted momentum on Treasuries. Different mechanic
  (cross-sectional vs time-series) and different universe.

Credit-spread momentum trades a *credit-cycle* signal that is
materially decoupled from rate momentum: in risk-on regimes
spreads tighten and IG credit out-performs Treasuries; in risk-off
regimes the reverse. The 6/0 momentum on credit captures the
persistence of the credit cycle.

## Why 6/0 instead of 12/1

Jostova et al. find the most reliable corporate-bond momentum
signal at a 6-month lookback with **no skip**, unlike the 12/1
convention from Moskowitz/Ooi/Pedersen (2012) for Treasuries. The
mechanism is microstructural: corporate-bond returns have shorter
autocorrelation than Treasury returns because dealer inventory
turnover and primary-issuance schedules drive most of the trailing-
return predictability. Skipping a month on corporate bonds
discards information that *is* predictive (unlike on Treasuries
where the 1-month skip excludes short-term reversal noise).

## Published rules

For each month-end *t*:

1. Compute trailing 6-month log return on the IG corporate bond
   proxy.
2. Sign-of-return signal: +1 if positive, −1 if negative, 0 if
   ``|return| ≤ threshold``.
3. Hold one month, rebalance monthly.

| Parameter | Default | Notes |
|---|---|---|
| `lookback_months` | `6` | Jostova et al. §III recommendation |
| `skip_months` | `0` | no skip on corporates |
| `threshold` | `0.0` | filter marginal signals |

## In-sample period (Jostova et al. 2013)

* Data: 1973–2008 monthly corporate bond returns
* IG, HY, and full-spectrum panels separately
* Cross-sectional Sharpe of 0.6–1.0 across IG and HY sleeves
* Single-asset (broad IG ETF proxy) is expected to come in at
  Sharpe 0.3–0.5, similar to single-asset Treasury momentum

## Implementation deviations from Jostova et al. (2013)

1. **Single-asset application** rather than the cross-sectional
   ranking on individual bonds in the paper. Cross-sectional
   ranking on individual corporate bonds requires bond-by-bond
   pricing data which is not in scope for Phase 2. The single-asset
   application on a broad IG ETF (LQD) is the closest tractable
   approximation.
2. **No bid-ask or short-borrow model** — bridge applies
   ``commission_bps``, but corporate-bond bid-ask spreads are
   wider than Treasury spreads and the bridge does not reflect
   this. Real-feed Session 2H benchmarks should add a corporate-
   bond-specific bid-ask layer.

## Known replications and follow-ups

* **Asness, Moskowitz, Pedersen (2013) §V** — cross-asset
  momentum. Bond momentum applies to corporates alongside
  sovereigns.
* **Israel, Palhares, Richardson (2018)** — "Common Factors in
  Corporate Bond Returns", JFE. Refined factor model that
  includes credit-spread momentum as a tradeable factor.
