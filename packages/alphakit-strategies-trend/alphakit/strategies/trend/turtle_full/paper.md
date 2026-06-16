# Book — Way of the Turtle (Faith 2003)

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

## Background

In 1983 Richard Dennis recruited a group of novice traders (the
"Turtles") and trained them on a fully systematic trend-following
program. Over the next four years the Turtles collectively earned
more than $100 million using a simple Donchian breakout system with
ATR-based position sizing. Curtis Faith — one of the original Turtles —
published the complete ruleset in 2003 after the program had been
retired and the rules went public.

## The rules in brief

1. **Two breakout systems running in parallel:**
   * System 1: 20-day entry, 10-day exit.
   * System 2: 55-day entry, 20-day exit.
2. **Position sizing by ATR (``N``):**
   * ``N = 20-day average true range``
   * Unit size ``= 1% of account / (N × $-per-point)``
   * Add another unit at every ½N favourable move, up to 4 units.
3. **Stops at 2N from the entry price.**
4. **Skip rule for System 1:** if the previous System 1 trade was a
   winner, skip the next breakout signal.
5. **Correlation / risk limits** cap gross exposure per market group.

## In-sample period

* Live trading, 1983–1988, Dennis's proprietary program.
* OOS performance since 2003 (when the rules became public) has been
  weaker than the Turtle-era numbers.

## Implementation deviations (Phase 1)

See the module docstring in `strategy.py`. Short version: no ATR
sizing, no skip rule, no pyramiding, no correlation caps. The core
economic signal (combine System 1 and System 2 breakout states) is
preserved. Phase 4 will add `turtle_full_atr` with the full sizing
framework.
