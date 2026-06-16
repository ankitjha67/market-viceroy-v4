# bxmp_overlay — CBOE BXMP-aligned Monthly Call+Put Overlay (Reframed Wheel)

CBOE BXMP-aligned monthly overlay: long underlying + short ATM
call (BXM rule) + short 5 % OTM put with cash collateral
(PUT-aligned). Phase 2 reframe of the practitioner "wheel"
strategy under the honesty framework — see
[`docs/phase-2-amendments.md`](../../../../../../docs/phase-2-amendments.md)
2026-05-01 entry.

> First trading day of each calendar month, simultaneously write
> a 1-month ATM call AND a 1-month 5 % OTM put against the long
> underlying. Hold both legs through expiry, roll on the next
> month's first trading day. Output: long underlying (+1.0) +
> short call leg (-1.0 / +1.0) + short put leg (-1.0 / +1.0)
> via discrete_legs Amount semantics on both option legs.

## Quickstart

```python
from alphakit.strategies.options import BXMPOverlay

strategy = BXMPOverlay(underlying_symbol="SPY")
# Mode 1 / Mode 2 contract mirrors covered_call_systematic +
# cash_secured_put_systematic combined. Three-instrument book
# in Mode 1 (underlying + call leg + put leg).
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `underlying_symbol` | `"SPY"` | Column name for the underlying |
| `call_otm_pct` | `0.0` | OTM offset for the call write (BXM canonical = ATM) |
| `put_otm_pct` | `0.05` | OTM offset for the put write (PUT-aligned 5 % OTM) |
| `chain_feed` | `None` | Explicit feed override |

## Documentation

* [Foundational + primary citations](paper.md) — Whaley (2002) +
  Israelov-Nielsen (2014). Includes the wheel-to-BXMP reframe
  rationale and the three-instrument-book construction.
* [Known failure modes](known_failures.md) — whipsaw rallies +
  selloffs, vol-of-vol spikes (**2× scaled** vs single-leg
  siblings), cluster overlap with covered_call_systematic /
  cash_secured_put_systematic / bxm_replication, composition-
  wrapper transparency.
* [Synthetic benchmark](benchmark_results.json) —
  Mode 2 buy-and-hold-of-SPY baseline.

## Tests

```bash
uv run pytest packages/alphakit-strategies-options/alphakit/strategies/options/bxmp_overlay/tests
```
