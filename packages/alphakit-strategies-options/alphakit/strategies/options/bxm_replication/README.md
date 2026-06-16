# bxm_replication — Canonical CBOE BXM Index Replication

Whaley 2002 BXM index methodology — exactly-ATM monthly call
write on synthetic option chains. Composition wrapper over
[`covered_call_systematic`](../covered_call_systematic/) with
`otm_pct = 0.0` fixed and metadata redirected at the Whaley 2002
sole anchor.

> First trading day of each calendar month, write a 1-month ATM
> call against a long-underlying position. Hold through expiry,
> roll on the next month's first trading day. Output: long
> underlying (+1.0) + short ATM call leg (-1.0 on writes, +1.0
> on closes via discrete_legs Amount semantics).

## Quickstart

```python
from alphakit.strategies.options import BXMReplication

strategy = BXMReplication(underlying_symbol="SPY")
# Same Mode 1 / Mode 2 contract as covered_call_systematic.
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `underlying_symbol` | `"SPY"` | Column name for the underlying |
| `chain_feed` | `None` | Explicit feed override |

(No `otm_pct` parameter — it is fixed at `0.0` per Whaley 2002
BXM rules. For the practitioner-aligned 2 % OTM variant, see
`covered_call_systematic`.)

## Documentation

* [Citation](paper.md) — Whaley (2002) sole anchor. Includes
  Differentiation table vs `covered_call_systematic` and the
  Bridge Integration cross-reference.
* [Known failure modes](known_failures.md) — strong-rally drag,
  vol-of-vol spikes, **strong cluster overlap with
  `covered_call_systematic`** (ρ ≈ 0.95-1.00), composition-
  wrapper transparency.
* [Synthetic benchmark](benchmark_results.json) —
  Mode 2 buy-and-hold-of-SPY baseline.

## Tests

```bash
uv run pytest packages/alphakit-strategies-options/alphakit/strategies/options/bxm_replication/tests
```
