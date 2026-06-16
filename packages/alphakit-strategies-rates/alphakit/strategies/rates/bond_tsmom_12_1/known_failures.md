# Known failure modes — bond_tsmom_12_1

> "Dies in 2022 rate shock" beats silence. Every AlphaKit strategy
> must document the regimes where it underperforms, so that users can
> size it intelligently and avoid surprise drawdowns.

Single-asset 12/1 time-series momentum on a long-duration bond
proxy. The strategy will **lose money** in the regimes below. None
of these are bugs — they are the cost of a uni-directional
single-asset momentum trade, with no cross-sectional or multi-asset
diversification.

## 1. Sharp regime turns (2022 H1)

The 2022 rate shock was the textbook failure mode: the 12/1 signal
went into the year long bonds (consistent with the 2020–2021 yield
decline), then took 3–6 months to flip short as yields rose. The
bond-only single-asset version of the strategy (this implementation)
posted approximately **−15% to −25%** over Jan–Jun 2022 against TLT.

Expected behaviour for bond_tsmom_12_1 in H1 2022:
* Drawdown of 15–25% before the signal flips short
* Late-year recovery as the short position pays off through Q4

## 2. Range-bound, low-vol bond markets (2017, 2019)

When the 11-month lookback window straddles a regime change, the
signal flips repeatedly month-to-month. Single-asset application
amplifies the cost: every flip is a full ±1 reversal of the book,
not a vol-scaled adjustment.

Expected behaviour in low-vol bond regimes:
* Sharpe of 0.0 to −0.5
* High monthly turnover (4–6 flips per year)
* Drawdowns of 5–10% from peak

Mitigation: raise the `threshold` parameter to 0.005 or 0.01 to
require a non-trivial trailing return before activating the signal.
This trades signal latency for fewer whipsaws.

## 3. Single-asset under-performance vs the diversified book

Asness §V reports Sharpe ratios of 0.7–1.0 for the **diversified**
G10 bond-momentum book. The single-country (US 10Y) sub-strategy
implemented here is in the 0.4–0.6 range out-of-sample (per Asness
Table III). The single-asset shortfall is structural — it reflects
the absence of cross-country diversification, not an implementation
bug.

Users who need higher Sharpe should run this strategy in a portfolio
alongside `g10_bond_carry` (which adds cross-country dispersion) and
the trend family's `tsmom_12_1` (which adds cross-asset
diversification).

## 4. Duration approximation bias (FRED-only environments)

When the strategy is fed a price series derived from FRED's `DGS10`
constant-maturity yield via the duration approximation
``bond_return ≈ -duration × Δy`` (see `paper.md`), the **level** of
returns is biased downward by the omitted carry term (yield × dt ≈
30–40 bps/month at current rates) and biased upward by the omitted
convexity term at large yield moves (≈ 10 bps/month at 50 bps Δy).

The **sign** of the 11-month cumulative return is dominated by the
duration × Δy term, so the signal is robust to the approximation.
But P&L attribution is not — real-feed benchmarks (Session 2H)
should prefer TLT total-return prices. The synthetic-fixture
benchmark in this folder uses TLT-profile fixture data and is
therefore unaffected by this caveat.

## 5. Cluster correlation with other rates strategies

This strategy will exhibit **ρ > 0.7** with several other rates
strategies in the family that also have systematic duration
exposure when bond markets are trending — specifically:

* `duration_targeted_momentum` — same momentum signal, different
  vol-scaling; expected ρ ≈ 0.85
* `bond_carry_rolldown` — carry and momentum tend to align in
  positively-sloped regimes; expected ρ ≈ 0.5
* `real_yield_momentum` — momentum on TIPS real yields tracks
  nominal momentum closely outside of inflation surprises; expected
  ρ ≈ 0.6

These overlaps are expected and will be surfaced by the cluster
analysis script in Session 2H. Phase 2 master plan §10 documents
the cluster-risk acceptance bar; correlations above 0.95 trigger
deduplication review, between 0.7–0.95 are acknowledged but
shippable.

## 6. Asset-specific blow-ups

A single-asset momentum book has no diversification by construction.
If TLT (or whichever single bond proxy is fed) suffers an
idiosyncratic shock — e.g. a Treasury auction failure, a sovereign
credit downgrade, a flash liquidity event — the strategy is fully
exposed. The 12/1 lookback means the position is held for at least
one month before any signal change.

## Regime performance (reference, single-asset 10Y momentum, gross of fees)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Disinflation tail (2008 GFC) | 2007-06 – 2009-06 | ~0.8 | −6% |
| Range-bound (2017) | 2017-01 – 2017-12 | ~−0.4 | −5% |
| Rate shock (2022 H1) | 2022-01 – 2022-06 | ~−1.5 | −22% |
| Trend recovery (2022 H2) | 2022-07 – 2022-12 | ~1.5 | −4% |
| Reversal (2023) | 2023-01 – 2023-12 | ~−0.6 | −9% |

(Reference ranges from the Asness Table III single-country bond
sub-strategy and from CTA-reported bond sleeves; the in-repo
benchmark is the authoritative source for this implementation —
see [`benchmark_results.json`](benchmark_results.json).)
