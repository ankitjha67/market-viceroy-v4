# put_skew_premium — Risk-Reversal Short OTM Put + Long OTM Call

⚠ **SUBSTRATE CAVEAT:** synthetic chain has flat IV by
construction; the put-skew premium this strategy targets does
NOT exist in the synthetic substrate. Strategy ships as
faithful methodology implementation; Phase 3 with Polygon
required for proper evaluation.

Bakshi-Kapadia-Madan 2003 foundational + Garleanu-Pedersen-
Poteshman 2009 primary.

> First trading day of each calendar month, write a 1-month
> 5 % OTM put (short) + buy a 1-month 5 % OTM call (long) —
> the canonical "risk reversal" trade. Hold to expiry.

## Documentation

* [paper.md](paper.md) — citations, structure, **substrate
  caveat warning**.
* [known_failures.md](known_failures.md) — substrate-caveat
  load-bearing failure mode (§1) + tail-risk regimes.

## Tests

```bash
uv run pytest packages/alphakit-strategies-options/alphakit/strategies/options/put_skew_premium/tests
```
