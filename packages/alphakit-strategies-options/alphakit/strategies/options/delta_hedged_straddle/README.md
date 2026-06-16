# delta_hedged_straddle — Long ATM Straddle With Daily Delta Hedge

Black-Scholes 1973 foundational + Carr-Wu 2009 primary. The
**long-vol counterparty** to short-vol siblings. Expected
NEGATIVE return per Carr-Wu's empirical VRP finding.

> First trading day of each calendar month, write a long ATM
> call + long ATM put (straddle). Hold through monthly expiry.
> Each in-position bar, daily-delta-hedge by setting the
> underlying weight to `-net_delta_t` (offset). Output: time-
> varying TargetPercent on the underlying + 2 long-leg discrete
> dispatches.

## Quickstart

```python
from alphakit.strategies.options import DeltaHedgedStraddle
strategy = DeltaHedgedStraddle()
# IMPORTANT: must call make_legs_prices BEFORE generate_signals
# to populate the per-cycle metadata used by the daily delta hedge.
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `underlying_symbol` | `"SPY"` | Underlying column |
| `chain_feed` | `None` | Explicit feed override |

## Documentation

* [paper.md](paper.md) — Black-Scholes (1973) + Carr-Wu (2009).
* [known_failures.md](known_failures.md) — VRP cost in
  quiet-vol regimes (expected behaviour, not a bug),
  daily-rebalance turnover drag, cluster overlap with
  `gamma_scalping_daily` (ρ ≈ 0.85-0.95), stateful coupling
  caveats.
* [Synthetic benchmark](benchmark_results.json).

## Tests

```bash
uv run pytest packages/alphakit-strategies-options/alphakit/strategies/options/delta_hedged_straddle/tests
```
