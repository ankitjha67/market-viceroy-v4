# gamma_scalping_daily — Daily Gamma Scalping (Sinclair 2008 Practitioner Framing)

Hull-White 1987 foundational + Sinclair 2008 primary. Composition
wrapper over [`delta_hedged_straddle`](../delta_hedged_straddle/)
with the practitioner-framing metadata (Sinclair 2008
*Volatility Trading*, Chapter 7).

> Identical trade mechanic to `delta_hedged_straddle`. Daily
> delta-hedged long ATM straddle. Long-vol VRP counterparty —
> expected NEGATIVE return per Sinclair / Carr-Wu / Hull-White.

## Quickstart

```python
from alphakit.strategies.options import GammaScalpingDaily
strategy = GammaScalpingDaily()
# Same usage pattern as DeltaHedgedStraddle:
# IMPORTANT — call make_legs_prices BEFORE generate_signals.
```

## Documentation

* [paper.md](paper.md) — Hull-White (1987) + Sinclair (2008).
  Includes the academic-vs-practitioner-framing differentiation
  table.
* [known_failures.md](known_failures.md) — Inherits all failure
  modes from `delta_hedged_straddle/known_failures.md`. Strong
  cluster ρ ≈ 0.95-1.00 with the parent strategy by design.

## Tests

```bash
uv run pytest packages/alphakit-strategies-options/alphakit/strategies/options/gamma_scalping_daily/tests
```
