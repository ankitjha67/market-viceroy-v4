# Paper — Frog in the Pan (Da, Gurun & Warachka 2014)

## Citation

> Da, Z., Gurun, U. G. & Warachka, M. (2014).
> **Frog in the pan: continuous information and momentum.**
> *The Review of Financial Studies*, 27(7), 2171–2218.
> [https://doi.org/10.1093/rfs/hhu003](https://doi.org/10.1093/rfs/hhu003)

```bibtex
@article{da2014frog,
  title   = {Frog in the pan: Continuous information and momentum},
  author  = {Da, Zhi and Gurun, Umit G and Warachka, Mitch},
  journal = {The Review of Financial Studies},
  volume  = {27},
  number  = {7},
  pages   = {2171--2218},
  year    = {2014},
  doi     = {10.1093/rfs/hhu003}
}
```

## Abstract

> The frog-in-the-pan (FIP) hypothesis predicts that investors
> under-react to information arriving in small continuous bits. Such
> continuous information generates stronger momentum than does
> discrete information because investors' limited attention means they
> notice small but steady changes less readily than sudden ones. Using
> the frequency of daily price moves as a proxy for the degree to which
> information arrives continuously, we find that stocks with continuous
> information experience momentum twice as large as those with discrete
> information, and that the continuous-information momentum effect
> persists for up to three years after portfolio formation.

## Information-discreteness (ID) definition

Over a formation window of ``F`` days, let ``pct_pos`` and ``pct_neg``
be the fractions of days with positive and negative simple returns.
Then:

> ID = sign(cumulative_return) × (pct_neg − pct_pos)

ID ∈ [−1, +1]. Low |ID| ⇒ continuous information.

## Published parameters

| Parameter | Paper | AlphaKit default |
|---|---|---|
| Formation | 12 months (252 days) | 11 months × 21 days |
| Skip | 1 month | 1 month |
| Decile | top/bottom 10% on double-sort (momentum × ID) | `top_pct=0.1` on continuity-weighted momentum |
| Rebalance | monthly | monthly |

## Implementation deviations

1. **Single-sort** on the combined signal `cum_return × (1 − |ID|)`
   rather than the paper's double-sort. The double-sort requires a
   larger universe than the ETF panel we ship for Phase 1 demos; the
   single-sort collapses to the same picks on small universes.
2. **21 trading days per month** rather than the actual month length,
   so the rolling window is stationary across the panel.

## In-sample period

* 1927–2007 CRSP NYSE/AMEX/NASDAQ common stocks, monthly rebalance.
