# short_strangle_monthly — 2-Leg Short-Vol Monthly Strangle

Coval/Shumway 2001 foundational + Bondarenko 2014 primary.
Iron condor minus the protective wings.

> First trading day of each calendar month, write a 2-leg short
> strangle: short OTM put + short OTM call (default 10 % OTM both).
> Hold both legs through expiry, roll on the next month's first
> trading day. Output: 0 underlying weight (pure-options trade) +
> 2-leg discrete dispatch via Amount semantics.

## Quickstart

```python
from alphakit.strategies.options import ShortStrangleMonthly
strategy = ShortStrangleMonthly()  # 10% OTM both legs by default
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `underlying_symbol` | `"SPY"` | Column name for the underlying |
| `put_otm` | `0.10` | OTM offset for the short put leg |
| `call_otm` | `0.10` | OTM offset for the short call leg |
| `chain_feed` | `None` | Explicit feed override |

## Documentation

* [Citations + bridge integration](paper.md) — Coval/Shumway
  (2001) + Bondarenko (2014).
* [Known failure modes](known_failures.md) — uncapped tails on
  sustained directional moves, vol-of-vol spikes (markedly worse
  than iron condor), cluster overlap with `iron_condor_monthly`
  (ρ ≈ 0.85-0.95).
* [Synthetic benchmark](benchmark_results.json) —
  Mode 2 degenerate baseline.

## Tests

```bash
uv run pytest packages/alphakit-strategies-options/alphakit/strategies/options/short_strangle_monthly/tests
```
