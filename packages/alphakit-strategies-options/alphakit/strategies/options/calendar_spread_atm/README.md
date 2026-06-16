# calendar_spread_atm — ATM Calendar Spread (Front-Back Term Structure)

Goyal-Saretto 2009 sole anchor. Term-structure-normalisation
trade: short front-month ATM call + long back-month ATM call.

> First trading day of each calendar month, write a calendar
> spread: short ATM call (~30-day expiry) + long ATM call
> (~60-day expiry, same strike). Both close at front-month
> expiry. Output: 0 underlying weight + 2-leg discrete dispatch
> via Amount semantics (front: -1/+1, back: +1/-1).

## Quickstart

```python
from alphakit.strategies.options import CalendarSpreadATM
strategy = CalendarSpreadATM()
```

## Documentation

* [paper.md](paper.md) — Goyal-Saretto (2009).
* [known_failures.md](known_failures.md) — vol crashes,
  term-structure inversion, distinct cluster (ρ ≈ 0.30-0.55
  with most siblings).

## Tests

```bash
uv run pytest packages/alphakit-strategies-options/alphakit/strategies/options/calendar_spread_atm/tests
```
