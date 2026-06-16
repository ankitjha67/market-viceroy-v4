# Paper — Common Risk Factors in Currency Markets

> Lustig, H., Roussanov, N. & Verdelhan, A. (2011). Common Risk
> Factors in Currency Markets. *Review of Financial Studies*, 24(11),
> 3731-3777. DOI: 10.1093/rfs/hhr068.

```bibtex
@article{lustig2011common,
  title   = {Common Risk Factors in Currency Markets},
  author  = {Lustig, Hanno and Roussanov, Nikolai and Verdelhan, Adrien},
  journal = {Review of Financial Studies},
  volume  = {24},
  number  = {11},
  pages   = {3731--3777},
  year    = {2011},
  doi     = {10.1093/rfs/hhr068}
}
```

## Summary

Lustig, Roussanov, and Verdelhan document that sorting currencies by
forward discount (a proxy for interest-rate differential) produces a
cross-sectional spread — the "carry factor" — that earns positive
average excess returns. High-yielding currencies appreciate in
expectation (violating uncovered interest parity), delivering both
the interest-rate differential and capital gains, until a "carry
crash" unwinds the position.

## Phase 1 proxy

The StrategyProtocol provides only close prices, not interest rates.
This implementation uses the trailing 63-day return as a carry
proxy: currencies that have been appreciating are treated as
"high carry." This is a known simplification (see ADR-001). In
production, replace with actual forward discount data.

## Canonical parameters

| Parameter | Lustig et al. | AlphaKit default |
|---|---|---|
| Carry signal | Forward discount | Trailing 63-day return (proxy) |
| Long basket | Top 3 | 3 |
| Short basket | Bottom 3 | 3 |
| Universe | G10 currencies | 9 G10 pairs vs USD |

## In-sample period

Lustig et al. tested on G10 + EM currencies, 1953-2009.
