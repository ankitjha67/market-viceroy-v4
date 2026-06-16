# variance_risk_premium_synthetic — Short ATM Straddle (Carr-Wu §2 Approximation)

Bondarenko 2014 foundational + Carr-Wu 2009 §2 primary.
2-leg ATM-straddle approximation of the multi-strike
variance-swap-replication formula.

> First trading day of each calendar month, write a SHORT ATM
> straddle (short ATM call + short ATM put). Hold both legs
> through expiry, roll on the next month's first trading day.
> Output: 0 underlying weight + 2-leg discrete dispatch via
> Amount semantics (-1 at write, +1 at close on both legs).

## Quickstart

```python
from alphakit.strategies.options import VarianceRiskPremiumSynthetic
strategy = VarianceRiskPremiumSynthetic()
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `underlying_symbol` | `"SPY"` | Underlying column |
| `chain_feed` | `None` | Explicit feed override |

(No `otm_pct` parameter — both legs are fixed at ATM per the
Carr-Wu §2 ATM-straddle approximation. For OTM variants, see
`short_strangle_monthly`.)

## Documentation

* [paper.md](paper.md) — Bondarenko (2014) + Carr-Wu (2009) §2.
  Documents the 2-leg approximation honestly.
* [known_failures.md](known_failures.md) — uncapped tails on
  directional moves, vol-of-vol spikes, **2-leg-approximation
  caveat** (this is NOT literal Carr-Wu replication — Phase 3
  with Polygon ships full multi-strike).
* [Synthetic benchmark](benchmark_results.json) —
  Mode 2 degenerate baseline.

## Tests

```bash
uv run pytest packages/alphakit-strategies-options/alphakit/strategies/options/variance_risk_premium_synthetic/tests
```
