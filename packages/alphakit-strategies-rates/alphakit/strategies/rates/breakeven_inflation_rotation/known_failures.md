# Known failure modes — breakeven_inflation_rotation

> Inflation-expectation rotations are a *macro* trade. They can stay
> wrong for the entire duration of an inflation regime. The 2021–2022
> inflation shock is the canonical recent example: breakeven was
> "elevated" all year and the strategy was short-TIPS the whole
> way, eating losses as actual inflation kept printing high.

TIPS vs nominal Treasury rotation on the z-score of the price-spread
proxy. The strategy will lose money in the regimes below.

## 1. Persistent inflation regime change (2021–2022)

When inflation regime changes (e.g. post-pandemic supply shocks,
2021 Q3 onwards), breakeven rises and stays elevated — the z-score
pins above +1σ for 18 months as actual inflation prints follow
breakeven up. The strategy enters a short-TIPS rotation expecting
mean-reversion that doesn't arrive.

Expected behaviour during 2021-2022:

* Strategy short-TIPS / long-nominal from mid-2021 (z first crosses
  +1σ as breakeven re-prices)
* TIPS materially out-perform nominal as inflation realises higher
  than the elevated expectation
* Loss of 8-15% before the strategy finally exits when breakeven
  *peaks* and starts coming down (mid-2022)

This is the deepest known weakness. Mitigation:

* Pair the strategy with an inflation-momentum overlay that filters
  rotations away from the inflation trend (Phase 3 candidate).
* Or accept the regime-change risk and size the strategy modestly.

## 2. Missing inflation-swap hedge

FLL's pure arbitrage uses inflation swaps to strip the inflation
exposure from the long-TIPS leg. This implementation does not
have access to inflation swap data, so it trades the *unhedged*
TIPS-vs-nominal pair. The unhedged version conflates two signals:

* **Mean-reversion of breakeven** (what we want to capture)
* **Surprise inflation realisation** (residual exposure)

In tranquil inflation regimes (CPI close to consensus) the residual
is small. In regime shocks (2008-2009 deflation scare, 2021-2022
inflation shock, 2020 March panic) the residual dominates.

Real-feed Session 2H benchmark should add an inflation-swap data
adapter and a hedged variant of this strategy.

## 3. ETF basket vs constant-maturity mismatch

TIP (iShares TIPS Bond ETF) holds TIPS across the maturity spectrum
with effective duration ≈ 7.5 years. IEF holds 7-10Y nominals with
effective duration ≈ 8.0 years. A 50 bps parallel shift in real
yields therefore moves TIP by 7.5 × 50 = 375 bps and IEF by 400
bps — a 25 bps residual on each ±1.0 notional unit per shift.

Mitigation: real-feed Session 2H runs should use FRED's `DFII10`
(10Y TIPS yield) and `DGS10` (10Y nominal yield) with the duration
approximation, matching the maturities exactly.

## 4. TIPS liquidity and on-the-run premium

TIPS markets are less liquid than nominal Treasuries; bid-ask
spreads widen during stress. ETF prices can deviate from NAV by
50-100 bps during liquidity events (2008 Q4, 2020 March). The
strategy treats ETF prices as fair-value reflective; in practice
the entry/exit moments around liquidity events have higher slippage
than the bridge's ``commission_bps`` parameter assumes.

## 5. Cluster correlation with sibling strategies

* `real_yield_momentum` (Session 2D Commit 9) — momentum on TIPS
  real yields directly. Expected ρ ≈ 0.5 in inflation-regime-stable
  periods (when breakeven moves with real yields), lower otherwise.
* `bond_tsmom_12_1` — single-asset momentum on the long bond.
  Expected ρ ≈ 0.2-0.4 depending on the dominant signal in the
  current regime.
* `bond_carry_rolldown` — outright duration overlay; this strategy
  is approximately duration-neutral by construction so expected ρ
  is close to zero.

None of these cross 0.95.

## 6. Asymmetric tail risk

Inflation surprises are *more* asymmetric than other macro shocks:

* A 1% upside surprise to inflation (e.g. 2021 supply shock) costs
  the short-TIPS rotation 8-10% over a year
* A 1% downside surprise (e.g. 2009 deflation scare) costs the
  long-TIPS rotation similarly

Both tails happen approximately once per decade. The strategy
should be sized so that each tail is survivable.

## Regime performance (reference, gross of fees, equal-weighted TIP/IEF rotation)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| 2008-09 deflation scare and reversal | 2008-09 – 2009-12 | ~1.4 | −5% |
| Post-crisis QE-supported breakeven | 2010-2014 | ~0.5 | −7% |
| 2015-19 stable inflation | 2015-2019 | ~0.3 | −4% |
| 2020 March COVID dislocation | 2020-03 – 2020-06 | ~0.8 | −6% |
| 2021-22 inflation regime shift | 2021-06 – 2022-09 | ~−1.2 | −15% |
| 2023-25 normalisation | 2023-2025 | ~0.4 | −5% |

(Reference ranges from FLL (2014) Table 4 single-leg returns and
practitioner reports; the in-repo benchmark is authoritative for
this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
