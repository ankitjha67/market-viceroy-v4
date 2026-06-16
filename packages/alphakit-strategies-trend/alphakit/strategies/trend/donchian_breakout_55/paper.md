# Paper — 55/20 Donchian Breakout (Turtle System 2)

Primary citation:
> Donchian, R. D. (1960). *High Finance in Copper*. Financial Analysts
> Journal, 16(6), 133–142.
> [DOI](https://doi.org/10.2469/faj.v16.n6.133)

Practitioner reference:
> Faith, C. M. (2003). *Way of the Turtle: The Secret Methods that
> Turned Ordinary People into Legendary Traders*. McGraw-Hill.
> ISBN 978-0071486644.

```bibtex
@book{faith2003way,
  title     = {Way of the Turtle: The Secret Methods that Turned Ordinary People into Legendary Traders},
  author    = {Faith, Curtis},
  publisher = {McGraw-Hill},
  year      = {2003},
  isbn      = {978-0071486644}
}
```

## Context

Richard Dennis's *Turtles* (1983) used **two independent Donchian
breakout systems** running in parallel:

* **System 1:** 20-day entry, 10-day exit (aggressive, fast).
* **System 2:** 55-day entry, 20-day exit (slow, our default here).

If a trade in System 1 was profitable, System 2 would skip the next
breakout to avoid double-counting. This strategy ships only System 2
by itself; the full multi-system variant lives in `turtle_full`.

Curtis Faith's *Way of the Turtle* (2003) is the canonical public
reference for the Turtle rules.
