# Known failure modes — real_yield_momentum

> Real-yield momentum has the same failure modes as nominal-yield
> momentum (whipsaw at regime turns, range-bound bleed, single-asset
> concentration risk) plus a few unique to TIPS specifically:
> liquidity scarcity in stress regimes and inflation-accrual leakage.

12/1 TSMOM on TIPS real-yield-derived bond returns. Will lose
money in the regimes below.

## 1. Same regime risks as nominal TSMOM (2022 H1)

Real yields rose alongside nominal yields during 2022. The strategy
went into the year long TIPS (consistent with 2020-2021 real-yield
decline), then took 3-6 months to flip short. Drawdown of 12-20%
in H1 2022 against TIP.

## 2. TIPS liquidity squeeze (2008 Q4, 2020 March)

TIPS markets are less liquid than nominal Treasuries; stress
regimes amplify the liquidity discount. During 2008 Q4 and 2020
March, TIPS prices dropped sharply (real yields spiked) even as
nominal yields fell, because TIPS *liquidity* deteriorated rather
than because real yields fundamentally changed. The strategy
interprets this as a real-yield trend and goes short TIPS, just
in time for the liquidity normalisation rally.

Mitigation: filter signal entries by rolling realised vol of the
TIPS price series — when vol spikes outside historical norms,
classify the regime as "liquidity stress" and pause new entries.
Phase 3 candidate.

## 3. Inflation-accrual leakage in the proxy

The TIPS principal accrues inflation linearly over time. The
duration-derived bond-return proxy::

    real_bond_return ≈ -D × Δ(real_yield)

ignores this accrual (which is typically 30-50 bps/month at
current inflation). The accrual biases *all* TIPS returns upward
by a constant amount and therefore does not bias the *sign* of
any 11-month cumulative return — but the proxy under-states
absolute returns by ~3-6% per year. P&L attribution from the
proxy is therefore conservative.

## 4. Cluster correlation with sibling strategies

* `bond_tsmom_12_1` — nominal bond TSMOM. Expected ρ ≈ 0.6-0.8 in
  regime-stable periods, decoupling during inflation shocks.
* `breakeven_inflation_rotation` — trades the difference. When
  breakeven moves materially, real-yield momentum and breakeven
  rotation overlap; expected ρ ≈ 0.3-0.5.
* `bond_carry_rolldown` — duration overlay; expected ρ ≈ 0.3-0.5
  when the TIPS curve is steep.

None of these cross 0.95.

## 5. Single-asset under-performance vs the diversified book

Asness §V reports ~0.7-1.0 Sharpe on the *diversified* G10 bond-
momentum book. Single-asset US TIPS momentum is expected to come
in at 0.3-0.5 Sharpe, similar to the single-asset US 10Y nominal
TSMOM. The single-asset shortfall is structural.

## Regime performance (reference, gross of fees, single-asset 10Y TIPS momentum)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-crisis era (2003-07) | 2003-01 – 2007-06 | ~0.4 | −5% |
| GFC (2008-2009) | 2008-01 – 2009-06 | ~−0.6 | −18% |
| QE-era trend (2010-2014) | 2010-01 – 2014-12 | ~0.6 | −7% |
| 2020 March COVID dislocation | 2020-03 – 2020-06 | ~−1.0 | −12% |
| 2021-22 inflation regime shift | 2021-06 – 2022-09 | ~−0.8 | −18% |
| 2023-25 normalisation | 2023-2025 | ~0.4 | −6% |

(Reference ranges from the Asness Table III bond-only sub-strategy
applied to TIPS-equivalent return series; the in-repo benchmark is
authoritative for this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
