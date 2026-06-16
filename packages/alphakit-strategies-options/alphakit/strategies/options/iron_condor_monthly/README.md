# iron_condor_monthly — 4-Leg Defined-Risk Short-Vol Monthly Iron Condor

CBOE CNDR-aligned 4-leg iron-condor write on synthetic option
chains (ADR-005). Hill et al. 2006 foundational + CBOE CNDR
Iron Condor Index methodology primary.

> First trading day of each calendar month, write a 4-leg
> iron condor: short put (5 % OTM), long put (10 % OTM,
> protective wing), short call (5 % OTM), long call (10 % OTM,
> protective wing). Hold all 4 legs through expiry, roll on the
> next month's first trading day. Output: 4-leg discrete dispatch
> via discrete_legs Amount semantics with signed weights (-1 for
> shorts, +1 for longs at write; opposite at close).

## Quickstart

```python
from alphakit.strategies.options import IronCondorMonthly

strategy = IronCondorMonthly()
# 4-instrument book in Mode 1 (4 leg columns required in prices).
# Mode 2 fallback is degenerate (no trade — iron condor needs all 4 legs).
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `underlying_symbol` | `"SPY"` | Column name for the underlying |
| `short_put_otm` | `0.05` | OTM offset for the short put leg |
| `long_put_otm` | `0.10` | OTM offset for the long put protective wing |
| `short_call_otm` | `0.05` | OTM offset for the short call leg |
| `long_call_otm` | `0.10` | OTM offset for the long call protective wing |
| `chain_feed` | `None` | Explicit feed override |

Constraint: `long_put_otm > short_put_otm` and
`long_call_otm > short_call_otm` (protective wings are deeper
OTM than the short legs). Validation raises `ValueError` if
violated.

## Documentation

* [Foundational + primary citations](paper.md) — Hill et al.
  (2006) survey + CBOE CNDR methodology. Includes the 4-leg
  bridge integration explanation (first 4-leg strategy in
  Session 2F).
* [Known failure modes](known_failures.md) — sustained
  directional moves through short strikes, vol-of-vol spikes
  (less severe than uncapped variants due to wing protection),
  cluster overlap with `short_strangle_monthly` (ρ ≈ 0.85-0.95),
  4-leg substrate bias cancellation.
* [Synthetic benchmark](benchmark_results.json) —
  Mode 2 degenerate baseline (zero trade, zero return).

## Tests

```bash
uv run pytest packages/alphakit-strategies-options/alphakit/strategies/options/iron_condor_monthly/tests
```
