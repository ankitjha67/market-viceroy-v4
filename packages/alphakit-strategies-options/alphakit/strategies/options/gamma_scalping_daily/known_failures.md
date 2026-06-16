# Known failure modes — gamma_scalping_daily

> Phase 2 practitioner-framing of daily delta-hedged straddle —
> Hull-White 1987 foundational + Sinclair 2008 primary. Composition
> wrapper over `delta_hedged_straddle` (Commit 9). Inherits all
> known failure modes from the parent.

## 1. Identical to `delta_hedged_straddle` failure modes

Cross-reference [delta_hedged_straddle/known_failures.md](../delta_hedged_straddle/known_failures.md):

* §1 Quiet-vol regimes — VRP cost (negative expected return)
* §2 Vol crash from elevated levels (post-spike normalisation)
* §3 Daily-rebalance turnover drag
* §6 Stateful-coupling caveat (make_legs_prices side effect)
* §7 Synthetic-chain substrate caveat (Greeks BS-computed, sigma
  frozen per cycle)
* §8 Standard-benchmark-runner mode caveat (degenerate)
* §9 Calendar-month-start writes vs. third-Friday writes
* §10 yfinance passthrough assumption (Session 2H verification)

## 2. Strong cluster overlap with `delta_hedged_straddle`

ρ ≈ 0.95-1.00 — identical trade mechanic, different citation
framing.

This is **not an accidental cluster** — it is the deliberate
academic-vs-practitioner parametric variant pattern. Both ship
on main: `delta_hedged_straddle` (Carr-Wu 2009 academic VRP-
measurement framing) and `gamma_scalping_daily` (Sinclair 2008
practitioner-trading framing).

Cluster-detection methodology (Phase 2 master plan §6) will
surface this pair at v0.2.0; the documentation here is the
authoritative explanation.

## 3. Composition-wrapper transparency

`GammaScalpingDaily` is a thin composition wrapper over
`DeltaHedgedStraddle`. The leg-pricing, lifecycle detection,
delta computation, and bridge dispatch are all delegated to the
inner instance. Bug fixes in `DeltaHedgedStraddle` flow through
to this strategy automatically.

Metadata (`name`, `paper_doi`, `family`) is independent and
reflects the Sinclair 2008 practitioner framing.

## 4. Practitioner vs academic framing — what changes

The strategy's **trade behaviour is identical** to
`delta_hedged_straddle`. What differs:

* `name`: `gamma_scalping_daily` vs `delta_hedged_straddle`
* `paper_doi`: ISBN of Sinclair 2008 vs DOI of Carr-Wu 2009
* Documentation emphasis: practitioner trading mechanic vs
  academic VRP measurement

If a user runs both strategies on the same fixture, the
backtests should produce essentially identical equity curves
(up to floating-point noise from independent backtest runs).
This is enforced by the integration test
`test_gamma_scalping_matches_delta_hedged_straddle`.

## 5. Why ship both

Two motivations for shipping both as separate strategies:

1. **Citation diversity.** Users searching for "gamma scalping"
   in literature find Sinclair 2008; users searching for
   "variance risk premium" find Carr-Wu 2009. Two slugs make
   both citations discoverable.
2. **Future divergence.** Phase 3 may parameterise these
   differently (e.g., gamma_scalping_daily could ship intraday
   rebalance frequencies vs delta_hedged_straddle's monthly
   write cycle). Keeping them separate now preserves that
   future flexibility.

## 6. Inherited caveats (full pass-through)

All caveats documented in
[`delta_hedged_straddle/known_failures.md`](../delta_hedged_straddle/known_failures.md)
apply to this strategy verbatim.
