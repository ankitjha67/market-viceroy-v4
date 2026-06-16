# vix_term_structure_roll — VIX Spot-vs-Front-Month Basis Trade

Whaley 2009 foundational + Simon-Campasano 2014 primary. Real
^VIX (yfinance equity passthrough) + VIX=F (yfinance-futures
passthrough) basis trade.

> Daily, compute basis = ^VIX − VIX=F. Long VIX=F when
> backwardation (basis > 0); short when contango. No options
> chains involved.

## Quickstart

```python
from alphakit.strategies.options import VIXTermStructureRoll
strategy = VIXTermStructureRoll()
# Universe: ^VIX (signal source) + VIX=F (traded leg)
```

## Documentation

* [paper.md](paper.md) — Whaley (2009) + Simon-Campasano (2014).
  Differentiation from Phase 1 ``vix_term_structure`` (RV proxy).
* [known_failures.md](known_failures.md) — stress flip whiplash,
  contango whipsaws, **yfinance ^-prefix passthrough assumption**.
* [Synthetic benchmark](benchmark_results.json) —
  fixture-fed metrics.

## Tests

```bash
uv run pytest packages/alphakit-strategies-options/alphakit/strategies/options/vix_term_structure_roll/tests
```
