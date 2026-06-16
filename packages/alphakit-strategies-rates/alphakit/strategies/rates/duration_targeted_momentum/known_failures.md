# Known failure modes — duration_targeted_momentum

> Cross-sectional bond momentum is highly regime-conditional. The
> strategy works well in trending macro environments and badly in
> transitions. Durham (2015) §VI documents the regime conditioning
> explicitly: most of the Sharpe is concentrated in two-thirds of
> the calendar months, and the remaining third has near-zero or
> negative skill.

Cross-sectional dollar-neutral momentum on duration-adjusted bond
returns. The strategy will lose money in the regimes below.

## 1. Regime transitions (2009 H1, 2020 H2, 2022 H1)

When the macro regime shifts abruptly, the trailing 12/1 return
captures the *previous* regime and ranks bonds by exposure to the
*old* trend just as the new trend arrives. The result is short-
duration bonds out-performing long-duration when the long-end is
about to outperform (or vice versa).

Expected behaviour during 2022 Q1 (rate-shock onset):

* Strategy goes into Q1 long TLT-rank, short SHY-rank (TLT had
  out-performed in 2021 due to flight-to-quality)
* Rate shock hits, TLT loses 20% in the quarter, SHY loses 1%
* Strategy posts ~−15% in Q1 alone

Mitigation: shorten ``lookback_months`` to 6 for faster regime
recognition, accepting more signal noise in stable regimes.

## 2. Coarse rank with N=3

Default panel has only 3 bonds (SHY/IEF/TLT). Cross-sectional rank
in N=3 is coarse: top, middle, bottom. The middle bond carries zero
weight, and the long/short pair is just (TLT, SHY) most of the time
— which collapses the strategy to "long the bond with higher
duration-adjusted momentum, short the other".

This is a known limitation of the small-panel implementation.
Expanding to a wider panel (5+ bonds via FRED constant-maturity
yields) restores rank granularity and is the intended path for
Session 2H real-feed benchmarks.

## 3. ETF basket vs CMT duration drift

The default ``durations`` are ETF effective durations, not CMT
durations. ETF effective durations drift as new bonds enter and
old bonds roll off. TLT's effective duration was 17.0 on average
over 2010-2020 but spiked to 18.5 during late-2020 (when long-end
yields were lowest) and fell to 16.0 during late-2022. The
strategy uses a fixed 17.0 from config; the duration-mismatch bias
varies by ±10% across the cycle.

Mitigation: re-estimate durations annually from the ETF prospectus
or from FRED yields. Real-feed Session 2H benchmark should pull
effective durations from the iShares fund pages.

## 4. Signal noise from coarse 12-1 monthly resampling

The strategy resamples to month-ends and computes monthly log
returns; a single noisy month-end print propagates into the 12-1
sum. Durham (2015) recommends robustness checks via 11/1 and 13/1
variants, which this implementation does not run. The
``lookback_months`` and ``skip_months`` parameters expose this
flexibility but the default 12/1 is the canonical choice.

## 5. Cluster correlation with sibling strategies

* `bond_tsmom_12_1` — *single-asset* version on a single bond.
  Expected ρ ≈ 0.5–0.8 when one bond dominates the cross-section,
  lower otherwise. Specifically: when SHY's 12-1 return is ranked
  bottom and TLT's is ranked top (typical bear-bond regimes), the
  strategy is short SHY / long TLT, which is highly correlated with
  the single-asset TLT TSMOM signal.
* `bond_carry_roll` (Phase 1 carry family) — cross-sectional carry
  without duration adjustment; expected ρ ≈ 0.4 in trending regimes.
* `g10_bond_carry` (Session 2D Commit 11) — cross-country carry;
  uncorrelated to US-only momentum (different country dispersion);
  expected ρ ≈ 0.0–0.2.

None of these cross 0.95.

## 6. Sub-strategy under-performance vs the diversified book

Durham (2015) reports a ~0.6 Sharpe on the 7-maturity-bucket
duration-adjusted ranking. The 3-ETF version implemented here is
expected to come in at 0.3–0.4 Sharpe due to the coarse rank. This
is a structural limitation, not an implementation bug. Expanding
the panel for Session 2H real-feed benchmarks should partially
close the gap.

## Regime performance (reference, gross of fees, dollar-neutral 3-ETF cross-sectional)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Bond bull market (2010–2012) | 2010-01 – 2012-12 | ~0.5 | −5% |
| QE-driven trend (2013–2015) | 2013-01 – 2015-12 | ~0.4 | −7% |
| Reach-for-yield (2016–2017) | 2016-01 – 2017-12 | ~−0.2 | −8% |
| Rate shock (2022) | 2022-01 – 2022-12 | ~−0.8 | −18% |
| Re-trend (2023–2025) | 2023-01 – 2025-06 | ~0.3 | −6% |

(Reference ranges from Durham §VI sub-period tables and from the
AQR bond TSMOM sleeve; the in-repo benchmark is authoritative for
this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
