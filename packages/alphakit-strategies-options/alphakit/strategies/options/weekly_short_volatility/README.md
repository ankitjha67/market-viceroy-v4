# weekly_short_volatility — 2-Leg Weekly Short-Vol Strangle (Reframed Weekly Theta Harvest)

Carr-Wu 2009 foundational + Bondarenko 2014 primary. Phase 2
reframe of practitioner `weekly_theta_harvest`.

> First trading day of each calendar week, write a 1-week 5 % OTM
> put + 5 % OTM call. Hold both legs through next-Friday expiry,
> roll on the next Monday. Output: 0 underlying weight (pure-
> options) + 2-leg discrete dispatch via Amount semantics.

## Quickstart

```python
from alphakit.strategies.options import WeeklyShortVolatility
strategy = WeeklyShortVolatility()
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `underlying_symbol` | `"SPY"` | Underlying column |
| `put_otm` | `0.05` | OTM offset for short put |
| `call_otm` | `0.05` | OTM offset for short call |
| `chain_feed` | `None` | Explicit feed override |

## Documentation

* [paper.md](paper.md) — Carr-Wu (2009) + Bondarenko (2014).
  Includes the weekly_theta_harvest → weekly_short_volatility
  reframe rationale.
* [known_failures.md](known_failures.md) — uncapped weekly tails,
  vol spikes, weekly-specific bid-ask amplification, cluster
  overlap with `short_strangle_monthly`.
* [Synthetic benchmark](benchmark_results.json) —
  Mode 2 degenerate baseline.

## Tests

```bash
uv run pytest packages/alphakit-strategies-options/alphakit/strategies/options/weekly_short_volatility/tests
```
