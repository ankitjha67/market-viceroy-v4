# cash_secured_put_systematic — Systematic 1-Month 5 % OTM Put Write

Single-leg systematic monthly cash-secured-put write on synthetic
option chains (ADR-005). Put-side analogue of
`covered_call_systematic`; cited on Whaley 2002 (foundational,
CBOE PUT index construction) and Israelov & Nielsen 2014 (primary,
put-call-parity decomposition).

> First trading day of each calendar month, write a 1-month 5 %
> OTM put against cash collateral. Hold through expiry, roll on
> the next month's first trading day. Output: long underlying
> (+1.0 cash collateral) + short put leg (−1.0 on writes, +1.0
> on closes via discrete_legs Amount semantics).

## Quickstart

```python
import pandas as pd
from alphakit.bridges import vectorbt_bridge
from alphakit.strategies.options import CashSecuredPutSystematic

strategy = CashSecuredPutSystematic(underlying_symbol="SPY", otm_pct=0.05)

underlying_prices: pd.Series = ...  # SPY closes, daily index
put_leg_prices = strategy.make_put_leg_prices(underlying_prices)
prices = pd.DataFrame({
    strategy.underlying_symbol: underlying_prices,
    strategy.put_leg_symbol:    put_leg_prices,
})

result = vectorbt_bridge.run(strategy=strategy, prices=prices)
print(f"Sharpe (CSP): {result.sharpe:.2f}")
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `underlying_symbol` | `"SPY"` | Column name for the underlying |
| `otm_pct` | `0.05` | OTM offset for the written put (decimal, ≤ 0.50) |
| `chain_feed` | `None` | Explicit feed override; lazy `FeedRegistry.get("synthetic-options")` |

See [`config.yaml`](config.yaml) and [`strategy.py`](strategy.py)
for the full configuration and implementation docstring.

## Documentation

* [Foundational + primary citations](paper.md) — Whaley (2002) and
  Israelov-Nielsen (2014). Includes the mandatory Data Fidelity
  note and the Bridge Integration section.
* [Known failure modes](known_failures.md) — strong-downside
  drawdowns, vol-of-vol spikes, **strong cluster overlap with
  Phase 1 `cash_secured_put_proxy`** (ρ ≈ 0.85-0.95) and with
  sibling `covered_call_systematic` (ρ ≈ 0.95-1.00 by put-call
  parity).
* [Synthetic benchmark](benchmark_results.json) —
  Mode 2 buy-and-hold-of-SPY baseline. Mode 1 full CSP P&L
  exercised in tests; standard benchmark runner waits on
  Session 2H.

## Tests

```bash
uv run pytest packages/alphakit-strategies-options/alphakit/strategies/options/cash_secured_put_systematic/tests
```
