# covered_call_systematic — Systematic 1-Month 2 % OTM Call Write

Single-leg systematic monthly covered-call write on synthetic
option chains (ADR-005). Implements the BXM-style construction of
Whaley (2002) with the 2 % OTM offset variant Israelov & Nielsen
(2014) study.

> First trading day of each calendar month, write a 1-month 2 %
> OTM call against a long-underlying position. Hold through expiry,
> roll on the next month's first trading day. Output: long
> underlying (+1.0) + short call leg (−1.0 on writes, +1.0 on
> closes via discrete_legs Amount semantics).

## Quickstart

```python
import pandas as pd
from alphakit.bridges import vectorbt_bridge
from alphakit.strategies.options import CoveredCallSystematic

# Mode 1 — full covered call (canonical, two-leg, end-to-end through bridge):
strategy = CoveredCallSystematic(underlying_symbol="SPY", otm_pct=0.02)

underlying_prices: pd.Series = ...  # SPY closes, daily index
call_leg_prices = strategy.make_call_leg_prices(underlying_prices)
prices = pd.DataFrame({
    strategy.underlying_symbol: underlying_prices,
    strategy.call_leg_symbol:   call_leg_prices,
})

# strategy.discrete_legs == (strategy.call_leg_symbol,) — the bridge
# dispatches SizeType.Amount for the call leg automatically.
result = vectorbt_bridge.run(strategy=strategy, prices=prices)
print(f"Sharpe (covered call): {result.sharpe:.2f}")

# Mode 2 — buy-and-hold approximation (standard benchmark runner):
prices_underlying_only = pd.DataFrame({"SPY": underlying_prices})
result_bh = vectorbt_bridge.run(strategy=strategy, prices=prices_underlying_only)
print(f"Sharpe (buy-and-hold approx.): {result_bh.sharpe:.2f}")
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `underlying_symbol` | `"SPY"` | Column name for the underlying |
| `otm_pct` | `0.02` | OTM offset for the written call (decimal, ≤ 0.50) |
| `chain_feed` | `None` | Explicit feed override; lazy `FeedRegistry.get("synthetic-options")` |

See [`config.yaml`](config.yaml) for the full default configuration
and [`strategy.py`](strategy.py) for the implementation docstring.

## `discrete_legs` integration

This strategy declares `discrete_legs = (call_leg_symbol,)` —
introduced for Session 2F (see
[`docs/phase-2-amendments.md`](../../../../../../docs/phase-2-amendments.md)
2026-05-01 entry "bridge architecture extension for
discrete-traded legs"). The `vectorbt_bridge` reads this via
`alphakit.core.protocols.get_discrete_legs` and dispatches
`SizeType.Amount` for the call leg, `SizeType.TargetPercent` for
the underlying. This keeps the written-and-held call short
position as a one-shot trade per cycle rather than continuously
rebalanced (which would produce runaway P&L as premium decays).

## Documentation

* [Foundational + primary citations](paper.md) — Whaley (2002) and
  Israelov-Nielsen (2014). Includes the mandatory Data Fidelity
  note about synthetic chains and the Bridge Integration section
  documenting `discrete_legs`.
* [Known failure modes](known_failures.md) — strong-rally drag,
  vol-of-vol spikes, **strong cluster overlap with Phase 1
  `covered_call_proxy`** (ρ ≈ 0.85-0.95), expected Session 2F
  sibling correlations.
* [Synthetic benchmark](benchmark_results.json) — fixture-
  based metrics. Real-feed Polygon verification deferred to Phase 3
  (ADR-004 stub).

## Tests

```bash
uv run pytest packages/alphakit-strategies-options/alphakit/strategies/options/covered_call_systematic/tests
```
