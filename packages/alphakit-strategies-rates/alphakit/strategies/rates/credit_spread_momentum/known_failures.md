# Known failure modes — credit_spread_momentum

> Credit momentum is reliable until it isn't. The 2008-09 GFC and
> 2020 March COVID dislocation are both instances where the
> credit-momentum signal pointed long IG just before spreads blew
> out. The signal eventually flips short but only after a 15-20%
> drawdown.

Single-asset 6/0 momentum on IG corporate bond returns. Will lose
money in the regimes below.

## 1. Credit cycle inflection (2007 Q4, 2020 February)

The 6-month trailing-return signal lags the credit cycle. It enters
the year long IG (consistent with the prior easy-credit regime),
then takes 4-6 months to flip short as spreads widen. Drawdown
during the cycle inflection can reach 15-20% on a single-asset IG
ETF.

Mitigation: pair with a credit-spread *level* signal that exits
the long position when spreads have already tightened to
historical lows (cycle-aware). Phase 3 candidate.

## 2. IG-vs-HY decoupling

In risk-off regimes IG and HY can decouple sharply: IG holds up
(flight-to-quality preserves IG demand) while HY collapses. The
single-asset IG strategy doesn't capture the HY signal that may
be more informative about underlying credit-cycle direction.

Real-feed Session 2H should run the strategy on both LQD (IG) and
HYG (HY) and compute the cross-sectional version on the pair.

## 3. Asset-specific microstructure shocks

LQD specifically has experienced large NAV-vs-price discounts
during liquidity stress (March 2020: LQD discount peaked at 5%
intraday). The strategy uses ETF prices, not NAV; large NAV-vs-
price gaps mean the trailing return reflects ETF microstructure
rather than underlying bond fundamentals.

## 4. Cluster correlation with sibling strategies

* `bond_tsmom_12_1` — sovereign 12/1 momentum. In risk-off regimes
  Treasuries rally and IG bleeds; the two strategies diverge.
  Expected ρ ≈ 0.2-0.4 averaged across regimes.
* `real_yield_momentum` — TIPS-derived momentum. Even less
  correlated with credit; expected ρ ≈ 0.1-0.3.
* `bond_carry_rolldown` and `g10_bond_carry` — different signal
  type entirely (carry vs momentum); expected ρ ≈ 0.1-0.2.

None of these cross 0.95.

## 5. Single-asset under-performance vs Jostova cross-section

Jostova et al. report Sharpe 0.6-1.0 on the cross-sectional
ranking of individual corporate bonds. Single-asset on a broad IG
ETF is expected to come in at 0.3-0.5 Sharpe — similar shortfall
to single-asset bond_tsmom_12_1 vs Asness §V's diversified G10
sleeve.

## Regime performance (reference, gross of fees, single-asset IG 6/0 momentum)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-crisis credit boom (2003-07) | 2003-01 – 2007-06 | ~0.7 | −5% |
| GFC (2008-09) | 2008-01 – 2009-12 | ~−0.6 | −19% |
| QE-era spread compression (2010-14) | 2010-01 – 2014-12 | ~0.6 | −7% |
| Energy-crisis credit shock (2015-16) | 2015-06 – 2016-06 | ~−0.4 | −9% |
| 2020 March COVID dislocation | 2020-02 – 2020-04 | ~−1.5 | −18% |
| 2022 rate shock | 2022-01 – 2022-12 | ~−0.7 | −12% |
| 2023-25 normalisation | 2023-2025 | ~0.4 | −5% |

(Reference ranges from the Jostova et al. (2013) IG sub-strategy
and from CreditSights / J.P. Morgan credit factor reports; the
in-repo benchmark is authoritative for this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
