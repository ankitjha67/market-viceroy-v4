# vix_3m_basis — VIX Spot vs 3-Month Constant-Maturity Basis (Reframed Front-Back Spread)

Whaley 2009 foundational + Alexander-Korovilas-Kapraun 2015
primary. Phase 2 reframe of `vix_front_back_spread`
(yfinance has no back-month VIX futures; reframed to the
spot-vs-3-month-CMI basis Alexander et al. study explicitly).

> Daily, compute basis = ^VIX − ^VIX3M. Long ^VIX3M when
> backwardation; short when contango. Composition wrapper over
> `VIXTermStructureRoll` with longer_symbol = ^VIX3M.

## Documentation

* [paper.md](paper.md) — Whaley (2009) + Alexander/Korovilas/
  Kapraun (2015). Reframe rationale and tenor differentiation
  from `vix_term_structure_roll`.
* [known_failures.md](known_failures.md) — **^VIX3M is an
  index, not tradeable** (real production needs VXZ ETN);
  cluster overlap with vix_term_structure_roll (ρ ≈ 0.55-0.75).

## Tests

```bash
uv run pytest packages/alphakit-strategies-options/alphakit/strategies/options/vix_3m_basis/tests
```
