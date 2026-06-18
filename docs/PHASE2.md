# Phase 2 — Strategy engine + validation gate: status

Phase 2 builds the **validation gate** (PRD FR-V2/V3/V4, BR-001): the machinery
that decides whether a strategy's edge is real enough to reach `active`
(allocatable). It enforces the **"validated, not proven"** rail (CLAUDE.md #4) —
`active` requires real-feed data AND a multi-stage pass; gross-positive alone
never qualifies; synthetic-fixture results can never be `active`.

## The gate (extends `alphakit-bench`, `validation/` subpackage)

A strategy is graded through every stage, then judged by pure decision rules:

| Stage | Module | Pass criterion |
|---|---|---|
| Cost-aware backtest | (vectorbt bridge) | net-positive after fees/slippage |
| Walk-forward | `walk_forward.py` | majority of rolling OOS windows positive (no look-ahead) |
| Regime-conditioned | `regime.py` | no regime Sharpe below the floor (HMM = Phase 5) |
| Deflated Sharpe | `deflated_sharpe.py` | PSR/DSR ≥ threshold after multiple-testing correction |
| Monte-Carlo | `monte_carlo.py` | bootstrap Sharpe CI lower bound > 0 |

`gate.decide()` maps these to **active / observe / failed**: synthetic → never
active; real + no OOS edge → failed; real + clears all stages → active; real but
inconclusive → observe. The decision logic is pure and exhaustively unit-tested.

No new heavy deps: deflated Sharpe uses `statistics.NormalDist` (no scipy),
Monte-Carlo uses numpy. MLflow is deferred; results persist to Postgres
(`strategy_gate_run`, migration `0002`) + each strategy's `benchmark_results.json`.

## Candidates (the honest reality)

Of 109 catalog strategies, **31 have real-feed data** (11 rates + 11 macro +
7 commodity + cot via yfinance/futures/FRED/CFTC). The other 78 are
synthetic-fixture and stay `observe` (never credible per the rails). Crypto
isn't a gate candidate (the CCXT governor caps ~500 bars, no date-range).

## Producing the gate verdicts (offline)

Real grading needs network (yfinance, unofficial) and a FRED key (4 macro
hybrids), so it runs **offline**, not in per-push CI (which tests the gate
*stages* deterministically on fixtures). Run the grader:

```bash
export FRED_API_KEY=...            # for the 4 yfinance+fred strategies
uv run python scripts/run_gate.py            # all 31 real-feed strategies
uv run python scripts/run_gate.py --limit 5  # smoke a few
```

It writes each verdict into the strategy's `benchmark_results.json` `gate` block
and prints the honest `active / observe / failed` summary. **The `active` count
is whatever genuinely survives — it may be well under 30, by design** (the gate
exists to fail overfit strategies). This count is reported from the run, never
tuned to hit a target (CLAUDE.md #4).

## Strategy Lab (data + API)

`GET /api/v1/strategies` (catalog + gate status + provenance + headline metrics)
and `GET /api/v1/strategies/{slug}` (full detail) surface the graded catalog.
The React Strategy Lab UI is Phase 4/8 — Phase 2 ships the data + API.

## Gates (local, Python 3.12.13)

- Suite + ≥85% coverage; `mypy --strict` clean; ruff clean. The gate-stage unit
  tests (deflated Sharpe vs known values, seeded Monte-Carlo, no-look-ahead
  walk-forward, exhaustive `decide` cases) run in per-push CI with no network.
- CI `integration` job: applies migration `0002` (`mv-migrate`) and runs the
  gate-results Postgres round-trip (FR-V3) alongside the journal + CCXT smokes.

## Deferred (out of Phase 2 scope)

HMM/Markov regime classifier (FR-S6, Phase 5); wiring the 78 synthetic
strategies to real feeds (Phase 3–6); MLflow; the React Strategy Lab UI
(Phase 4/8); the point-in-time CI leakage check (FR-V6, Phase 3).
