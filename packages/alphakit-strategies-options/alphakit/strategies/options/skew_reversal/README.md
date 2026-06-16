# skew_reversal — Conditional Short Put When Put-Skew Z-Score > Threshold

⚠ **SUBSTRATE CAVEAT:** synthetic chain has flat IV; trigger
NEVER fires; backtest is degenerate no-trade. Phase 3 with
Polygon required for proper evaluation.

Bakshi-Kapadia-Madan 2003 foundational + Garleanu-Pedersen-
Poteshman 2009 primary.

## Documentation

* [paper.md](paper.md) — substrate caveat warning + citations.
* [known_failures.md](known_failures.md) — substrate-caveat
  load-bearing failure mode (§1).

## Tests

```bash
uv run pytest packages/alphakit-strategies-options/alphakit/strategies/options/skew_reversal/tests
```
