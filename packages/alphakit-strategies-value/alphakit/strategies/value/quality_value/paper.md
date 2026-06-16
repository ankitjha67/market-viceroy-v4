# Paper — Quality Minus Junk

> Asness, C.S., Frazzini, A. & Pedersen, L.H. (2019). Quality Minus
> Junk. *Review of Accounting Studies*, 24, 34-112.
> DOI: [10.1007/s11142-018-9470-2](https://doi.org/10.1007/s11142-018-9470-2).

```bibtex
@article{asness2019quality,
  title   = {Quality Minus Junk},
  author  = {Asness, Clifford S. and Frazzini, Andrea and
             Pedersen, Lasse Heje},
  journal = {Review of Accounting Studies},
  volume  = {24},
  pages   = {34--112},
  year    = {2019},
  doi     = {10.1007/s11142-018-9470-2}
}
```

## Summary

Asness, Frazzini & Pedersen define quality as a composite of
profitability, growth, safety, and payout. A quality-minus-junk (QMJ)
factor goes long high-quality stocks and short low-quality ("junk")
stocks. The QMJ factor earns significant risk-adjusted returns globally
and complements the value factor: cheap, high-quality stocks outperform
expensive, low-quality stocks by a wide margin.

## Phase 1 proxy

Without fundamental data, quality and value are proxied as follows:

- **Value rank**: negative trailing 3-year (756-day) return (long-term
  reversal as cheapness proxy).
- **Quality rank**: composite of low trailing volatility (safety proxy)
  and positive trailing 1-year (252-day) momentum (profitability/growth
  proxy). Both components are ranked cross-sectionally and summed.
- **Combined rank**: sum of value rank and quality rank.

The quality proxy captures low-vol + momentum, not the accounting-based
profitability, growth, safety, and payout dimensions of the original
paper. See ADR-001.

## Canonical parameters

| Parameter | Asness et al. | AlphaKit default |
|---|---|---|
| Quality measure | Profitability + growth + safety + payout | Low-vol + momentum |
| Value measure | Book-to-market | 756-day reversal |
| Rebalance | Monthly | Monthly |

## In-sample period

Asness, Frazzini & Pedersen (2019): US equities 1957-2012, global
equities 1989-2012.
